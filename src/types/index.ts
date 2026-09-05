export interface LLMMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

export interface CodeGenerationRequest {
  prompt: string;
  language?: string;
  model?: string;
  provider?: string;
  temperature?: number;
  maxTokens?: number;
  systemPrompt?: string;
  messages?: LLMMessage[];
}

export interface CodeGenerationResponse {
  code: string;
  explanation: string;
  language: string;
  provider: string;
  model: string;
  usage?: {
    inputTokens: number;
    outputTokens: number;
    totalTokens: number;
  };
  executionTime: number;
}

export interface LLMProvider {
  name: string;
  models: string[];
  generate(request: CodeGenerationRequest): Promise<CodeGenerationResponse>;
  listModels(): Promise<string[]>;
  checkHealth(): Promise<boolean>;
}

export interface ProviderConfig {
  apiKey: string;
  baseUrl?: string;
  timeout?: number;
  maxRetries?: number;
}
