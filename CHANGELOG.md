# Changelog

## [0.1.0] - 2024-XX-XX

### Added
- Initial release of LayaMCP — HTTP MCP server wrapping the Laya decision engine
- Five tools: `laya_guard`, `laya_route`, `laya_moderate`, `laya_triage`, `laya_email`
- Plugin-style architecture: adding a tool = 1 file + 2 lines in the registry
- Custom exception hierarchy with defensive parsing (raises on malformed Laya output)
- Configuration via `LAYAMCP_*` env vars (HOST, PORT, PRELOAD_MODELS, LOG_LEVEL)
- Pytest test suite (33+ tests, mocked bridges — no GPU needed)
- AGENTS.md for AI coding agent instructions
- docs/ folder: ARCHITECTURE, TOOLS, CONFIGURATION, DEVELOPMENT, DEPLOYMENT, TROUBLESHOOTING
- integrations/lapis-memory-save-classified.ts — spec for LaPis-side integration