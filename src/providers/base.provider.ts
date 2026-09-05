import { LLMProvider, CodeGenerationRequest, CodeGenerationResponse, LLMMessage } from '../types/index.js';
import axios, { AxiosInstance } from 'axios';

export abstract class BaseProvider implements LLMProvider {
  protected apiKey: string;
  protected baseUrl: string;
  protected client: AxiosInstance;
  public name: string = 'base';
  public models: string[] = [];

  constructor(apiKey: string, baseUrl: string) {
    this.apiKey = apiKey;
    this.baseUrl = baseUrl;
    this.client = axios.create({
      baseURL: baseUrl,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });
  }

  protected buildSystemPrompt(language?: string): string {
    return `You are an expert code generation AI. Generate clean, well-documented, and optimized code.
${language ? `Language: ${language}\n` : ''}Provide the code first, followed by a brief explanation.`;
  }

  protected formatMessages(request: CodeGenerationRequest): LLMMessage[] {
    const messages: LLMMessage[] = [];

    if (request.systemPrompt) {
      messages.push({
        role: 'system',
        content: request.systemPrompt,
      });
    }

    if (request.messages) {
      messages.push(...request.messages);
    } else {
      messages.push({
        role: 'user',
        content: request.prompt,
      });
    }

    return messages;
  }

  abstract generate(request: CodeGenerationRequest): Promise<CodeGenerationResponse>;
  abstract listModels(): Promise<string[]>;
  abstract checkHealth(): Promise<boolean>;
}
