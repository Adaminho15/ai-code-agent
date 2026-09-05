import { BaseProvider } from './base.provider.js';
import { CodeGenerationRequest, CodeGenerationResponse } from '../types/index.js';

export class CohereProvider extends BaseProvider {
  public name = 'cohere';
  public models = [
    'command-r-plus',
    'command-r',
    'command',
  ];

  constructor(apiKey: string) {
    super(apiKey, 'https://api.cohere.ai/v1');
    this.client.defaults.headers['Authorization'] = `Bearer ${apiKey}`;
  }

  async generate(request: CodeGenerationRequest): Promise<CodeGenerationResponse> {
    const startTime = Date.now();
    const model = request.model || this.models[0];
    const messages = this.formatMessages(request);

    try {
      const response = await this.client.post('/chat', {
        model,
        chat_history: messages.slice(0, -1),
        message: messages[messages.length - 1].content,
        temperature: request.temperature || 0.7,
        max_tokens: request.maxTokens || 2000,
      });

      const content = response.data.text;
      const [code, explanation] = this.parseResponse(content);

      return {
        code,
        explanation,
        language: request.language || 'unknown',
        provider: this.name,
        model,
        usage: {
          inputTokens: response.data.meta?.tokens?.input_tokens || 0,
          outputTokens: response.data.meta?.tokens?.output_tokens || 0,
          totalTokens: (response.data.meta?.tokens?.input_tokens || 0) + (response.data.meta?.tokens?.output_tokens || 0),
        },
        executionTime: Date.now() - startTime,
      };
    } catch (error) {
      throw new Error(`Cohere error: ${error instanceof Error ? error.message : String(error)}`);
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
      await this.client.post('/chat', {
        message: 'ping',
      });
      return true;
    } catch {
      return false;
    }
  }
}
