/* Parse Markdown tokens, build DOM only. Model HTML is never executed. */
function safeWebURL(raw){try{const u=new URL(raw);return ['http:','https:'].includes(u.protocol)?u.href:null}catch{return null}}
function renderMarkdown(text){
  const root=document.createElement('div');root.className='markdown';
  const normalized=String(text).replace(/(?:<br\s*\/?\s*>|&lt;br\s*\/?\s*&gt;)/gi,'\n');
  if(!window.marked){root.textContent=normalized;return root}
  function nodes(tokens,host){for(const t of tokens||[]){let n;
    if(t.type==='space')continue;
    if(t.type==='image'){const url=safeWebURL(t.href);n=image({image_urls:url?[url]:[],persian_title:t.text||'تصویر کالا'});}
    else if(t.type==='link'){const url=safeWebURL(t.href);n=document.createElement(url?'a':'span');if(url){n.href=url;n.target='_blank';n.rel='noopener noreferrer';}nodes(t.tokens||[{type:'text',text:t.text}],n);}
    else if(t.type==='table'){n=document.createElement('div');n.className='table-scroll';const table=document.createElement('table');const tr=document.createElement('tr');for(const cell of t.header){const th=document.createElement('th');nodes(cell.tokens,th);tr.append(th)}table.append(tr);for(const row of t.rows){const tr=document.createElement('tr');for(const cell of row){const td=document.createElement('td');nodes(cell.tokens,td);tr.append(td)}table.append(tr)}n.append(table);}
    else if(t.type==='list'){n=document.createElement(t.ordered?'ol':'ul');for(const item of t.items){const li=document.createElement('li');nodes(item.tokens,li);n.append(li)}}
    else if(t.type==='html'){continue;}
    else if(t.type==='br'){n=document.createElement('br');}
    else if(t.type==='code'||t.type==='codespan'){n=document.createElement(t.type==='code'?'pre':'code');n.textContent=t.text;}
    else{const tags={paragraph:'p',heading:'h3',strong:'strong',em:'em',del:'del',blockquote:'blockquote',hr:'hr'};n=document.createElement(tags[t.type]||'span');if(t.tokens)nodes(t.tokens,n);else n.textContent=t.text||'';}
    host.append(n);
  }}
  nodes(marked.lexer(normalized,{gfm:true,breaks:true}),root);return root;
}
