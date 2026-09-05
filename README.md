# AI Code Agent 🤖

A powerful, multi-provider AI code generation application that works seamlessly with 10+ LLM providers.

## Features

✨ **Multi-Provider Support** - Use any of 10+ LLM providers:
- OpenRouter
- OpenAI (GPT-4, GPT-3.5)
- Anthropic (Claude)
- Cloudflare Workers AI
- HuggingFace
- Together.ai
- Replicate
- Groq
- Cohere
- And more...

🚀 **Instant Code Generation** - Generate production-ready code in seconds

📊 **Provider Switching** - Seamlessly switch between providers without changing your code

💾 **Batch Operations** - Generate multiple code snippets in parallel

📡 **Streaming Support** - Real-time code generation with Server-Sent Events

🏥 **Health Monitoring** - Check provider availability and status

## Installation

```bash
git clone https://github.com/Adaminho15/ai-code-agent.git
cd ai-code-agent
npm install
```

## Configuration

1. Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

2. Add your API keys:
```env
OPENAI_API_KEY=sk_your_key_here
ANTHROPIC_API_KEY=sk-ant-your_key_here
OPENROUTER_API_KEY=sk-or-your_key_here
CLOUDFLARE_API_KEY=your_key_here
CLOUDFLARE_ACCOUNT_ID=your_account_id
# ... add more provider keys as needed
```

## Usage

### Start the server

```bash
npm run dev     # Development mode with auto-reload
npm run build   # Build TypeScript
npm start       # Production mode
```

### API Endpoints

#### 1. Generate Code

**POST** `/generate`

```bash
curl -X POST http://localhost:3000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Write a function that calculates fibonacci",
    "language": "typescript",
    "provider": "openrouter",
    "model": "openai/gpt-4"
  }'
```

**Request Body:**
```json
{
  "prompt": "Write a function...",
  "language": "typescript",        // Optional
  "provider": "openrouter",        // Optional (uses default)
  "model": "openai/gpt-4",         // Optional (uses provider default)
  "temperature": 0.7,              // Optional
  "maxTokens": 2000,               // Optional
  "systemPrompt": "...",           // Optional
  "messages": []                   // Optional (for multi-turn)
}
```

**Response:**
```json
{
  "code": "function fibonacci(n) { ... }",
  "explanation": "This function calculates...",
  "language": "typescript",
  "provider": "openrouter",
  "model": "openai/gpt-4",
  "usage": {
    "inputTokens": 50,
    "outputTokens": 200,
    "totalTokens": 250
  },
  "executionTime": 1234
}
```

#### 2. List Available Providers

**GET** `/providers`

```bash
curl http://localhost:3000/providers
```

**Response:**
```json
{
  "providers": [
    {
      "name": "openrouter",
      "models": [
        "openai/gpt-4-turbo",
        "openai/gpt-4",
        "anthropic/claude-3-opus",
        "..."
      ]
    },
    {
      "name": "openai",
      "models": [
        "gpt-4-turbo-preview",
        "gpt-4",
        "gpt-3.5-turbo"
      ]
    }
  ]
}
```

#### 3. Stream Code Generation

**POST** `/generate-stream`

Same request body as `/generate`, returns Server-Sent Events stream:

```bash
curl -X POST http://localhost:3000/generate-stream \
  -H "Content-Type: application/json" \
  -d '{"prompt": "..."}'
```

**Streaming Response:**
```
data: {"status":"generating","message":"Starting code generation..."}
data: {"status":"code","code":"function hello() { ... }"}
data: {"status":"explanation","explanation":"This function..."}
data: {"status":"complete","response":{...}}
```

#### 4. Batch Generation

**POST** `/generate-batch`

```bash
curl -X POST http://localhost:3000/generate-batch \
  -H "Content-Type: application/json" \
  -d '{
    "requests": [
      {"prompt": "Write a hash function", "language": "python"},
      {"prompt": "Write a binary tree", "language": "go"},
      {"prompt": "Write a queue", "language": "rust"}
    ]
  }'
```

#### 5. Health Check

**GET** `/health`

```bash
curl http://localhost:3000/health
```

**Response:**
```json
{
  "status": "healthy",
  "providers": {
    "openrouter": true,
    "openai": true,
    "anthropic": true,
    "cloudflare": false
  }
}
```

## Supported Providers

| Provider | Models | Status |
|----------|--------|--------|
| OpenRouter | 100+ | ✅ Full Support |
| OpenAI | GPT-4, GPT-3.5 | ✅ Full Support |
| Anthropic | Claude 3 | ✅ Full Support |
| Cloudflare | Workers AI | ✅ Full Support |
| HuggingFace | Llama, Mistral | ✅ Full Support |
| Together.ai | Llama, Mistral | ✅ Full Support |
| Replicate | Meta, etc | ✅ Full Support |
| Groq | Mixtral, Llama | ✅ Full Support |
| Cohere | Command | ✅ Full Support |

## Advanced Usage

### Multi-turn Conversations

```bash
curl -X POST http://localhost:3000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "language": "python",
    "provider": "openrouter",
    "messages": [
      {"role": "user", "content": "Write a fibonacci function"},
      {"role": "assistant", "content": "def fibonacci(n)..."},
      {"role": "user", "content": "Now optimize it with memoization"}
    ]
  }'
```

### Custom System Prompts

```bash
curl -X POST http://localhost:3000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Write a React component",
    "language": "typescript",
    "systemPrompt": "You are a senior React architect. Write clean, production-ready code with best practices."
  }'
```

### Provider-Specific Model Selection

```bash
# Using GPT-4 via OpenRouter
curl -X POST http://localhost:3000/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "...", "provider": "openrouter", "model": "openai/gpt-4-turbo"}'

# Using Claude via Anthropic
curl -X POST http://localhost:3000/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "...", "provider": "anthropic", "model": "claude-3-opus-20240229"}'
```

## Development

```bash
# Install dependencies
npm install

# Run in development mode with auto-reload
npm run dev

# Build TypeScript
npm run build

# Run tests
npm test

# Lint
npm run lint

# Format
npm run format
```

## Architecture

```
src/
├── types/          # TypeScript interfaces and types
├── providers/      # LLM provider implementations
│   ├── base.provider.ts
│   ├── openrouter.provider.ts
│   ├── openai.provider.ts
│   ├── anthropic.provider.ts
│   ├── cloudflare.provider.ts
│   ├── huggingface.provider.ts
│   ├── together.provider.ts
│   ├── replicate.provider.ts
│   ├── groq.provider.ts
│   └── cohere.provider.ts
├── factory.ts      # Provider factory pattern
├── service.ts      # Business logic layer
└── index.ts        # Express API server
```

## Error Handling

The application includes comprehensive error handling:

```json
{
  "error": "Provider 'invalid' not found. Available: openrouter, openai, anthropic"
}
```

## Performance Tips

1. **Use appropriate models** - Use cheaper models for simple tasks
2. **Batch requests** - Use `/generate-batch` for multiple generations
3. **Stream results** - Use `/generate-stream` for real-time feedback
4. **Set reasonable timeouts** - Configure based on your needs
5. **Monitor provider health** - Check `/health` regularly

## License

MIT

## Contributing

Contributions welcome! Please feel free to submit a Pull Request.

## Support

For issues and questions, please open a GitHub issue.
