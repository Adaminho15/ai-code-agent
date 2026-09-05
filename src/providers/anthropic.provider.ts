import { BaseProvider } from './base.provider.js';
import { CodeGenerationRequest, CodeGenerationResponse } from '../types/index.js';

export class AnthropicProvider extends BaseProvider {
  public name = 'anthropic';
  public models = ['claude-3-opus-20240229', 'claude-3-sonnet-20240229', 'claude-3-haiku-20240307'];

  constructor(apiKey: string) {
    super(apiKey, 'https://api.anthropic.com/v1');
    this.client.defaults.headers['x-api-key'] = apiKey;
    this.client.defaults.headers['anthropic-version'] = '2023-06-01';
  }

  async generate(request: CodeGenerationRequest): Promise<CodeGenerationResponse> {
    const startTime = Date.now();
    const model = request.model || this.models[0];
    const messages = this.formatMessages(request);

    try {
      const systemPrompt = messages.find((m) => m.role === 'system')?.content || this.buildSystemPrompt(request.language);
      const chatMessages = messages.filter((m) => m.role !== 'system');

      const response = await this.client.post('/messages', {
        model,
        max_tokens: request.maxTokens || 2000,
        system: systemPrompt,
        messages: chatMessages,
      });

      const content = response.data.content[0].text;
      const [code, explanation] = this.parseResponse(content);

      return {
        code,
        explanation,
        language: request.language || 'unknown',
        provider: this.name,
        model,
        usage: {
          inputTokens: response.data.usage.input_tokens,
          outputTokens: response.data.usage.output_tokens,
          totalTokens: response.data.usage.input_tokens + response.data.usage.output_tokens,
        },
        executionTime: Date.now() - startTime,
      };
    } catch (error) {
      throw new Error(`Anthropic error: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  private parseResponse(content: string): [string, string] {
    const codeMatch = content.match(/```[\s\S]*?\n([\s\S]*?)\n```/);
    const code = codeMatch ? codeMatch[1].trim() : content;
    const explanation = content.replace(/```[\s\S]*?\n[\s\S]*?\n```/, '').trim();
    return [code, explanation || 'No explanation provided'];
  }

  async listModels(): Promise<string[]> {
    return this.models;
  }

  async checkHealth(): Promise<boolean> {
    try {
      await this.client.post('/messages', {
        model: this.models[0],
        max_tokens: 10,
        messages: [{ role: 'user', content: 'ping' }],
      });
      return true;
    } catch {
      return false;
    }
  }
}
