import { BaseProvider } from './base.provider.js';
import { CodeGenerationRequest, CodeGenerationResponse } from '../types/index.js';

export class TogetherProvider extends BaseProvider {
  public name = 'together';
  public models = [
    'meta-llama/Llama-2-70b-chat-hf',
    'mistralai/Mistral-7B-Instruct-v0.1',
    'NousResearch/Nous-Hermes-2-Mixtral-8x7B-DPO',
  ];

  constructor(apiKey: string) {
    super(apiKey, 'https://api.together.xyz/inference');
    this.client.defaults.headers['Authorization'] = `Bearer ${apiKey}`;
  }

  async generate(request: CodeGenerationRequest): Promise<CodeGenerationResponse> {
    const startTime = Date.now();
    const model = request.model || this.models[0];

    try {
      const response = await this.client.post('/chat/completions', {
        model,
        messages: this.formatMessages(request),
        max_tokens: request.maxTokens || 2000,
        temperature: request.temperature || 0.7,
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
          inputTokens: response.data.usage?.prompt_tokens || 0,
          outputTokens: response.data.usage?.completion_tokens || 0,
          totalTokens: response.data.usage?.total_tokens || 0,
        },
        executionTime: Date.now() - startTime,
      };
    } catch (error) {
      throw new Error(`Together error: ${error instanceof Error ? error.message : String(error)}`);
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
      return response.data.map((m: any) => m.name);
    } catch (error) {
      return this.models;
    }
  }

  async checkHealth(): Promise<boolean> {
    try {
      await this.client.post('/chat/completions', {
        model: this.models[0],
        messages: [{ role: 'user', content: 'ping' }],
        max_tokens: 10,
      });
      return true;
    } catch {
      return false;
    }
  }
}
