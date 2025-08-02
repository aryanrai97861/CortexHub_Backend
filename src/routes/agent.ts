import { Router, Request, Response } from 'express';
import { runPythonScript } from '../server'; // Import the helper function from server.ts
import path from 'path';

const router = Router();

// @route   POST /api/agents/run
// @desc    Receives a goal and triggers a LangGraph agent run
router.post('/run', async (req: Request, res: Response) => {
  const { goal } = req.body;

  if (!goal) {
    return res.status(400).json({ message: 'A goal is required to run the agent.' });
  }

  try {
    const pythonScriptPath = path.join(__dirname, '../../python_scripts/langgraph_agent.py');
    const pythonArgs = ['run_agent', goal];
    
    // The Python script will return a JSON object with a log array
    const pythonOutput = await runPythonScript(pythonScriptPath, pythonArgs);
    const result = JSON.parse(pythonOutput);

    res.status(200).json(result);
  } catch (error: any) {
    console.error('Error running agent:', error);
    res.status(500).json({ message: 'Failed to run agent.', error: (error as Error).message });
  }
});

export default router;
