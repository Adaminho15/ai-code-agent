import { BaseProvider } from './base.provider.js';
import { CodeGenerationRequest, CodeGenerationResponse } from '../types/index.js';

export class GroqProvider extends BaseProvider {
  public name = 'groq';
  public models = [
    'mixtral-8x7b-32768',
    'llama2-70b-4096',
    'gemma-7b-it',
  ];

  constructor(apiKey: string) {
    super(apiKey, 'https://api.groq.com/openai/v1');
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
      throw new Error(`Groq error: ${error instanceof Error ? error.message : String(error)}`);
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
