import express, { Request, Response } from 'express';
import dotenv from 'dotenv';
import { ProviderFactory } from './factory.js';
import { CodeGenerationService } from './service.js';
import { CodeGenerationRequest } from './types/index.js';

dotenv.config();

const app = express();
const port = process.env.PORT || 3000;

app.use(express.json());

// Initialize providers
ProviderFactory.initialize();

// Health check endpoint
app.get('/health', async (req: Request, res: Response) => {
  try {
    const health = await CodeGenerationService.checkHealth();
    const allHealthy = Object.values(health).every((h) => h);
    res.status(allHealthy ? 200 : 503).json({
      status: allHealthy ? 'healthy' : 'degraded',
      providers: health,
    });
  } catch (error) {
    res.status(500).json({ error: 'Health check failed' });
  }
});

// List available providers
app.get('/providers', (req: Request, res: Response) => {
  try {
    const providers = CodeGenerationService.getAvailableProviders();
    const details = providers.map((p) => ({
      name: p,
      models: CodeGenerationService.getModelsForProvider(p),
    }));
    res.json({ providers: details });
  } catch (error) {
    res.status(500).json({ error: String(error) });
  }
});

// Generate code endpoint
app.post('/generate', async (req: Request, res: Response) => {
  try {
    const request: CodeGenerationRequest = req.body;

    if (!request.prompt) {
      return res.status(400).json({ error: 'Prompt is required' });
    }

    const response = await CodeGenerationService.generate(request);
    res.json(response);
  } catch (error) {
    res.status(500).json({ error: String(error) });
  }
});

// Generate with streaming (Server-Sent Events)
app.post('/generate-stream', async (req: Request, res: Response) => {
  try {
    const request: CodeGenerationRequest = req.body;

    if (!request.prompt) {
      return res.status(400).json({ error: 'Prompt is required' });
    }

    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');

    res.write('data: ' + JSON.stringify({ status: 'generating', message: 'Starting code generation...' }) + '\n\n');

    const response = await CodeGenerationService.generate(request);

    res.write('data: ' + JSON.stringify({ status: 'code', code: response.code }) + '\n\n');
    res.write('data: ' + JSON.stringify({ status: 'explanation', explanation: response.explanation }) + '\n\n');
    res.write('data: ' + JSON.stringify({ status: 'complete', response }) + '\n\n');
    res.end();
  } catch (error) {
    res.write('data: ' + JSON.stringify({ status: 'error', error: String(error) }) + '\n\n');
    res.end();
  }
});

// Batch generation
app.post('/generate-batch', async (req: Request, res: Response) => {
  try {
    const requests: CodeGenerationRequest[] = req.body.requests || [];

    if (!Array.isArray(requests) || requests.length === 0) {
      return res.status(400).json({ error: 'Array of requests is required' });
    }

    const results = await Promise.all(
      requests.map((r) =>
        CodeGenerationService.generate(r).catch((error) => ({
          error: String(error),
          prompt: r.prompt,
        }))
      )
    );

    res.json({ results });
  } catch (error) {
    res.status(500).json({ error: String(error) });
  }
});

app.listen(port, () => {
  console.log(`🚀 AI Code Agent running on http://localhost:${port}`);
  console.log(`Available providers: ${CodeGenerationService.getAvailableProviders().join(', ')}`);
});
