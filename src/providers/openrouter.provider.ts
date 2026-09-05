import { BaseProvider } from './base.provider.js';
import { CodeGenerationRequest, CodeGenerationResponse } from '../types/index.js';

export class OpenRouterProvider extends BaseProvider {
  public name = 'openrouter';
  public models = [
    'openai/gpt-4-turbo',
    'openai/gpt-4',
    'openai/gpt-3.5-turbo',
    'anthropic/claude-3-opus',
    'anthropic/claude-3-sonnet',
    'google/palm-2',
    'meta-llama/llama-2-70b',
  ];

  constructor(apiKey: string) {
    super(apiKey, 'https://openrouter.io/api/v1');
    this.client.defaults.headers['Authorization'] = `Bearer ${apiKey}`;
    this.client.defaults.headers['HTTP-Referer'] = 'https://github.com/Adaminho15/ai-code-agent';
  }

  async generate(request: CodeGenerationRequest): Promise<CodeGenerationResponse> {
    const startTime = Date.now();
    const model = request.model || this.models[0];

    try {
      const response = await this.client.post('/chat/completions', {
        model,
        messages: this.formatMessages(request),
        temperature: request.temperature || 0.7,
        max_tokens: request.maxTokens || 2000,
      });

      const content = response.data.choices[0].message.content;
      const [code, explanation] = this.parseResponse(content);

      return {
        code,
        explanation,
        language: request.language || 'unknown',
        provider: this.name,
        model,
        usage: {
          inputTokens: response.data.usage.prompt_tokens,
          outputTokens: response.data.usage.completion_tokens,
          totalTokens: response.data.usage.total_tokens,
        },
        executionTime: Date.now() - startTime,
      };
    } catch (error) {
      throw new Error(`OpenRouter error: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  private parseResponse(content: string): [string, string] {
    const codeMatch = content.match(/```[\s\S]*?\n([\s\S]*?)\n```/);
    const code = codeMatch ? codeMatch[1].trim() : content;
    const explanation = content.replace(/```[\s\S]*?\n[\s\S]*?\n```/, '').trim();
    return [code, explanation || 'No explanation provided'];
  }

  async listModels(): Promise<string[]> {
    try {
      const response = await this.client.get('/models');
      return response.data.data.map((m: any) => m.id);
    } catch (error) {
      return this.models;
    }
  }

  async checkHealth(): Promise<boolean> {
    try {
      await this.client.get('/models');
      return true;
    } catch {
      return false;
    }
  }
}
