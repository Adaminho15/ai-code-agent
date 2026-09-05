import { BaseProvider } from './base.provider.js';
import { CodeGenerationRequest, CodeGenerationResponse } from '../types/index.js';

export class ReplicateProvider extends BaseProvider {
  public name = 'replicate';
  public models = [
    'meta/llama-2-70b-chat',
    'mistralai/mistral-7b-instruct-v0.1',
    'openai/whisper',
  ];

  constructor(apiKey: string) {
    super(apiKey, 'https://api.replicate.com/v1');
    this.client.defaults.headers['Authorization'] = `Token ${apiKey}`;
  }

  async generate(request: CodeGenerationRequest): Promise<CodeGenerationResponse> {
    const startTime = Date.now();
    const model = request.model || this.models[0];
    const messages = this.formatMessages(request);
    const prompt = messages.map((m) => `${m.role}: ${m.content}`).join('\n');

    try {
      const response = await this.client.post('/predictions', {
        version: model,
        input: {
          prompt,
          max_tokens: request.maxTokens || 2000,
          temperature: request.temperature || 0.7,
        },
      });

      let prediction = response.data;
      while (prediction.status === 'processing') {
        await new Promise((resolve) => setTimeout(resolve, 1000));
        const result = await this.client.get(`/predictions/${prediction.id}`);
        prediction = result.data;
      }

      const content = Array.isArray(prediction.output) ? prediction.output.join('') : prediction.output;
      const [code, explanation] = this.parseResponse(content);

      return {
        code,
        explanation,
        language: request.language || 'unknown',
        provider: this.name,
        model,
        executionTime: Date.now() - startTime,
      };
    } catch (error) {
      throw new Error(`Replicate error: ${error instanceof Error ? error.message : String(error)}`);
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
      await this.client.get('/account');
      return true;
    } catch {
      return false;
    }
  }
}
