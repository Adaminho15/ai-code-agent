import { BaseProvider } from './base.provider.js';
import { CodeGenerationRequest, CodeGenerationResponse } from '../types/index.js';

export class OpenAIProvider extends BaseProvider {
  public name = 'openai';
  public models = ['gpt-4-turbo-preview', 'gpt-4', 'gpt-3.5-turbo', 'gpt-3.5-turbo-16k'];

  constructor(apiKey: string) {
    super(apiKey, 'https://api.openai.com/v1');
    this.client.defaults.headers['Authorization'] = `Bearer ${apiKey}`;
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
      throw new Error(`OpenAI error: ${error instanceof Error ? error.message : String(error)}`);
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
      return response.data.data.filter((m: any) => m.id.includes('gpt')).map((m: any) => m.id);
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
