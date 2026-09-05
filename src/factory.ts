import { LLMProvider } from './types/index.js';
import {
  OpenRouterProvider,
  CloudflareProvider,
  AnthropicProvider,
  OpenAIProvider,
  HuggingFaceProvider,
  TogetherProvider,
  ReplicateProvider,
  GroqProvider,
  CohereProvider,
} from './providers/index.js';

export class ProviderFactory {
  private static providers: Map<string, LLMProvider> = new Map();

  static initialize() {
    const openrouterKey = process.env.OPENROUTER_API_KEY;
    if (openrouterKey) {
      this.providers.set('openrouter', new OpenRouterProvider(openrouterKey));
    }

    const cloudflareKey = process.env.CLOUDFLARE_API_KEY;
    const cloudflareAccountId = process.env.CLOUDFLARE_ACCOUNT_ID;
    if (cloudflareKey && cloudflareAccountId) {
      this.providers.set('cloudflare', new CloudflareProvider(cloudflareKey, cloudflareAccountId));
    }

    const anthropicKey = process.env.ANTHROPIC_API_KEY;
    if (anthropicKey) {
      this.providers.set('anthropic', new AnthropicProvider(anthropicKey));
    }

    const openaiKey = process.env.OPENAI_API_KEY;
    if (openaiKey) {
      this.providers.set('openai', new OpenAIProvider(openaiKey));
    }

    const huggingfaceKey = process.env.HUGGINGFACE_API_KEY;
    if (huggingfaceKey) {
      this.providers.set('huggingface', new HuggingFaceProvider(huggingfaceKey));
    }

    const togetherKey = process.env.TOGETHER_API_KEY;
    if (togetherKey) {
      this.providers.set('together', new TogetherProvider(togetherKey));
    }

    const replicateKey = process.env.REPLICATE_API_KEY;
    if (replicateKey) {
      this.providers.set('replicate', new ReplicateProvider(replicateKey));
    }

    const groqKey = process.env.GROQ_API_KEY;
    if (groqKey) {
      this.providers.set('groq', new GroqProvider(groqKey));
    }

    const cohereKey = process.env.COHERE_API_KEY;
    if (cohereKey) {
      this.providers.set('cohere', new CohereProvider(cohereKey));
    }
  }

  static getProvider(name: string): LLMProvider {
    const provider = this.providers.get(name.toLowerCase());
    if (!provider) {
      throw new Error(`Provider '${name}' not found. Available: ${Array.from(this.providers.keys()).join(', ')}`);
    }
    return provider;
  }

  static listProviders(): string[] {
    return Array.from(this.providers.keys());
  }

  static listModelsForProvider(providerName: string): string[] {
    return this.getProvider(providerName).models;
  }

  static getDefaultProvider(): LLMProvider {
    const defaultName = process.env.DEFAULT_PROVIDER || 'openrouter';
    return this.getProvider(defaultName);
  }

  static async checkProviderHealth(name: string): Promise<boolean> {
    try {
      return await this.getProvider(name).checkHealth();
    } catch {
      return false;
    }
  }

  static async checkAllHealth(): Promise<Record<string, boolean>> {
    const health: Record<string, boolean> = {};
    for (const name of this.listProviders()) {
      health[name] = await this.checkProviderHealth(name);
    }
    return health;
  }
}
