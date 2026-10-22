import json
import os
import time
import logging
from openai import OpenAI
from pydantic import Field
from backend.agent.query import Strict
from backend.agent.system_prompt import SYSTEM
from backend.agent.tools import execute, schemas

class ChatRequest(Strict):
    message: str = Field(min_length=1,max_length=3000)

class ChatResponse(Strict):
    assistant_message: str
    response_type: str
    components: list[dict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metrics: dict = Field(default_factory=dict)

def run(sid,message,client=None):
    from backend import app as a
    s=a.session(sid)
    history=s.get('history',[])[-12:]
    context=[{'role':'user','content':'Current session: '+json.dumps({k:v for k,v in s.items() if k!='history'},ensure_ascii=False)}]
    context+=history+[{'role':'user','content':message}]
    components=[]; traces=[]; seen=set(); usage=0; started=time.monotonic()
    timeout=min(120,max(5,float(os.getenv('OPENAI_TIMEOUT_SECONDS','45'))))
    answer='سرویس هوش مصنوعی در دسترس نیست. جست‌وجوی دستی و فیلترها همچنان قابل استفاده‌اند.'
    warning=[]; kind='ERROR'
    own=client is None
    try:
        model=os.getenv('OPENAI_MODEL','')
        if own:
            if not os.getenv('OPENAI_API_KEY') or not model: raise ValueError('AI_NOT_CONFIGURED')
            client=OpenAI(timeout=timeout,max_retries=0,base_url=os.getenv('OPENAI_BASE_URL') or None)
        for step in range(min(8,max(1,int(os.getenv('OPENAI_MAX_TOOL_ROUNDS','5'))))):
            remaining=timeout-(time.monotonic()-started)
            if remaining<=0: raise TimeoutError()
            response=client.responses.create(model=model,input=context,instructions=SYSTEM,tools=schemas(),
                max_output_tokens=min(4000,max(256,int(os.getenv('OPENAI_MAX_OUTPUT_TOKENS','1500')))),
                parallel_tool_calls=False,store=False,timeout=remaining)
            if response.usage: usage+=response.usage.total_tokens
            calls=[item for item in response.output if item.type=='function_call']
            if not calls:
                answer=response.output_text or 'لطفاً نیاز خود را دقیق‌تر مشخص کنید.'
                kind='RESULTS' if components else 'CLARIFICATION'
                break
            context.extend(item.model_dump(exclude_none=True) for item in response.output)
            if len(calls)>6: raise ValueError('TOO_MANY_TOOLS')
            for call in calls:
                tick=time.monotonic()
                try:
                    args=json.loads(call.arguments)
                    signature=call.name+json.dumps(args,sort_keys=True)
                    if signature in seen: raise ValueError('DUPLICATE_CALL')
                    seen.add(signature)
                    data=execute(call.name,args,sid)
                    # Keep structured catalog data, never model-created product cards.
                    components.append({'tool':call.name,'data':data,'arguments':args})
                    encoded=json.dumps(data,ensure_ascii=False)
                    if len(encoded)>30000:
                        # Trim model context, not the actual UI results.
                        if isinstance(data,list): data=data[:3]
                        elif isinstance(data,dict) and 'results' in data: data={**data,'results':data['results'][:3]}
                        if len(json.dumps(data,ensure_ascii=False))>30000:
                            data={'warning':'Detailed results displayed in UI. Request individual records.'}
                    result={'success':True,'data':data,'data_source':'torob_dataset'}
                except Exception as exc:
                    result={'success':False,'error_code':type(exc).__name__,'message':'Invalid tool arguments, missing data, or unsupported operation. Refine request.'}
                traces.append({'tool':call.name,'success':result['success'],'ms':round((time.monotonic()-tick)*1000,2)})
                context.append({'type':'function_call_output','call_id':call.call_id,'output':json.dumps(result,ensure_ascii=False)})
        else:
            answer='به سقف مراحل جست‌وجو رسیدم؛ نتایج بازیابی‌شده را بررسی کنید یا درخواست را دقیق‌تر کنید.'
            warning.append('TOOL_ROUND_LIMIT');kind='PARTIAL'
    except Exception as exc:
        warning.append('AI_NOT_CONFIGURED' if isinstance(exc,ValueError) and str(exc)=='AI_NOT_CONFIGURED' else 'AI_SERVICE_UNAVAILABLE')
        logging.getLogger(__name__).warning('Agent stopped: %s',type(exc).__name__)
    finally:
        if own and client is not None: client.close()
    # Reload after tool mutations, so history never overwrites updated preferences.
    s=a.session(sid)
    s['history']=(history+[{'role':'user','content':message},{'role':'assistant','content':answer}])[-12:]
    s['last_agent_trace']=traces
    a.save(sid,s)
    return ChatResponse(assistant_message=answer,response_type=kind,components=components,warnings=warning,
        metrics={'total_tokens':usage,'elapsed_ms':round((time.monotonic()-started)*1000,2),'tool_calls':traces})
