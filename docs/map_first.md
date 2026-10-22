# Map-first catalog status

The homepage `/` now opens an interactive Tehran map without a product search. `/chat` keeps the existing conversation UI. The map queries server-side viewport cells through `/api/map/clusters`; cells sum actual Product → Offer → Shop joins and split as zoom increases. No global offer limit is applied to aggregation. Shop browsing is paginated through `/api/map/stores` and `/api/stores/{shop_id}/offers`. Store cards are horizontal and come from source products/offers; shop-level installment labels appear only when recorded payment options contain an installment indication.

The map context (view, filter, selected shop/offer, selected point) is saved in browser session storage for chat navigation. Session and conversation persistence use the existing session ID. Location permission is requested only after a click. Map click selects a draggable point and requires another click to confirm.

The map uses bundled Leaflet code, while map tiles remain a network service. The browser used in this environment could not load external map tiles or the sampled `image.torob.com` image. Controls, markers, fallbacks and data joins can be tested locally, but actual external imagery is unverified. Configure a reachable tile provider before deployment. The OpenAI live call previously timed out; evidence-based model comparison feedback remains unverified.

`python -m scripts.map_first_smoke` validates SQL count parity at two zoom levels, geographic coverage counts, store/offer joins and eight browser widths. `python -m scripts.rendering_smoke` checks safe Markdown DOM, image fallback, location selection and overflow. No frontend build/typecheck exists for this static JavaScript frontend.
