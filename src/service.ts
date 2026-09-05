import { CodeGenerationRequest, CodeGenerationResponse } from './types/index.js';
import { ProviderFactory } from './factory.js';

export class CodeGenerationService {
  static async generate(request: CodeGenerationRequest): Promise<CodeGenerationResponse> {
    const provider = request.provider 
      ? ProviderFactory.getProvider(request.provider)
      : ProviderFactory.getDefaultProvider();

    return await provider.generate(request);
  }

  static getAvailableProviders(): string[] {
    return ProviderFactory.listProviders();
  }

  static getModelsForProvider(provider: string): string[] {
    return ProviderFactory.listModelsForProvider(provider);
  }

  static async checkHealth(): Promise<Record<string, boolean>> {
    return await ProviderFactory.checkAllHealth();
  }
}
