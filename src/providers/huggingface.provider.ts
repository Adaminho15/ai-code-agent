import { BaseProvider } from './base.provider.js';
import { CodeGenerationRequest, CodeGenerationResponse } from '../types/index.js';

export class HuggingFaceProvider extends BaseProvider {
  public name = 'huggingface';
  public models = [
    'meta-llama/Llama-2-70b-chat-hf',
    'mistralai/Mistral-7B-Instruct-v0.1',
    'bigcode/starcoder',
  ];

  constructor(apiKey: string) {
    super(apiKey, 'https://api-inference.huggingface.co/models');
    this.client.defaults.headers['Authorization'] = `Bearer ${apiKey}`;
  }

  async generate(request: CodeGenerationRequest): Promise<CodeGenerationResponse> {
    const startTime = Date.now();
    const model = request.model || this.models[0];
    const modelUrl = `${this.client.defaults.baseURL}/${model}`;

    try {
      const messages = this.formatMessages(request);
      const prompt = messages.map((m) => `${m.role}: ${m.content}`).join('\n');

      const response = await this.client.post(modelUrl, {
        inputs: prompt,
        parameters: {
          max_new_tokens: request.maxTokens || 2000,
          temperature: request.temperature || 0.7,
        },
      });

      const content = response.data[0]?.generated_text || '';
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
      throw new Error(`HuggingFace error: ${error instanceof Error ? error.message : String(error)}`);
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
      await this.client.post(`${this.client.defaults.baseURL}/${this.models[0]}`, {
        inputs: 'ping',
      });
      return true;
    } catch {
      return false;
    }
  }
}
