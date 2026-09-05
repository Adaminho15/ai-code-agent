import { BaseProvider } from './base.provider.js';
import { CodeGenerationRequest, CodeGenerationResponse } from '../types/index.js';

export class CloudflareProvider extends BaseProvider {
  public name = 'cloudflare';
  public models = [
    '@cf/meta/llama-2-7b-chat-int8',
    '@cf/mistral/mistral-7b-instruct-v0.1',
    '@cf/thebloke/neural-chat-7b-v3-1-awq',
  ];
  private accountId: string;

  constructor(apiKey: string, accountId: string) {
    super(apiKey, `https://api.cloudflare.com/client/v4/accounts/${accountId}/ai/run`);
    this.accountId = accountId;
    this.client.defaults.headers['Authorization'] = `Bearer ${apiKey}`;
  }

  async generate(request: CodeGenerationRequest): Promise<CodeGenerationResponse> {
    const startTime = Date.now();
    const model = request.model || this.models[0];

    try {
      const response = await this.client.post('', {
        messages: this.formatMessages(request),
      });

      const content = response.data.result?.response || '';
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
      throw new Error(`Cloudflare error: ${error instanceof Error ? error.message : String(error)}`);
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
      const response = await this.client.get(
        `https://api.cloudflare.com/client/v4/accounts/${this.accountId}/ai/models/search`
      );
      return response.data.result.map((m: any) => m.name);
    } catch (error) {
      return this.models;
    }
  }

  async checkHealth(): Promise<boolean> {
    try {
      await this.client.post('', { messages: [{ role: 'user', content: 'ping' }] });
      return true;
    } catch {
      return false;
    }
  }
}
