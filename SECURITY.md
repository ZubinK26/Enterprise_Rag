## Security

This repository ships a **local demo**: no hardened auth, auditing, encryption-at-rest beyond OS defaults, or production network controls.

### Reporting a vulnerability

If you discover a vulnerability that still matters in demo context (**secret leakage vectors, insecure defaults in CI, accidental credential logging**), please open a GitHub Issue marked **SECURITY** or contact the repo owner privately through their GitHub profile.

### Project-specific cautions

- **Never publish real API keys.** Keep `.env` local and scoped (rotate keys shared in chats).  
- **Do not ingest regulated / customer data** without legal review—the bundled Markdown is synthetic.  

For Google AI / Gemini key handling, refer to Google’s docs: [Gemini OpenAI-compatible API](https://ai.google.dev/gemini-api/docs/openai).
