# iRecommend Client

Client applications live here so they can be detached from the backend and deployed independently.

Clients communicate with the backend through HTTP APIs only. They should not import backend services, connect to Supabase directly, or require backend secrets.

Current client:

- `streamlit/` - current research/demo frontend for persona exploration, review simulation, and recommendations.

Reserved for later:

- `nextjs/` - reserved for a later polished frontend. It is not implemented yet.
