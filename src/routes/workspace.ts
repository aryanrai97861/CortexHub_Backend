// backend/src/routes/workspace.ts

import { Router, Request, Response } from 'express';
import Workspace from '../models/Workspace';
import DocumentModel from '../models/Document';
import { v4 as uuidv4 } from 'uuid'; // For generating unique invite links

const router = Router();

// @route   POST /api/workspaces/create
// @desc    Creates a new workspace and returns an invite link
router.post('/create', async (req: Request, res: Response) => {
  const { workspaceName } = req.body;

  if (!workspaceName) {
    return res.status(400).json({ message: 'Workspace name is required.' });
  }

  // NOTE: In a real app, you would get the ownerId from the authenticated user's session.
  // Since we're skipping auth, we'll use a placeholder ownerId.
  const ownerId = '00000000-0000-0000-0000-000000000001'; // Placeholder User ID

  try {
    const newWorkspace = await Workspace.create({
      name: workspaceName,
      ownerId: ownerId, // This will fail if a User with this ID doesn't exist.
      inviteLink: uuidv4(), // Generate a unique invite link
    });

    res.status(201).json({
      message: 'Workspace created successfully!',
      workspaceId: newWorkspace.id,
      inviteLink: newWorkspace.inviteLink,
    });
  } catch (error) {
    console.error('Error creating workspace:', error);
    res.status(500).json({ message: 'Failed to create workspace.', error: (error as Error).message });
  }
});


// @route   GET /api/workspaces/join/:inviteLink
// @desc    Finds a workspace by invite link and returns its details
router.get('/join/:inviteLink', async (req: Request, res: Response) => {
  const { inviteLink } = req.params;

  try {
    const workspace = await Workspace.findOne({
      where: { inviteLink: inviteLink },
      // Optional: Include members in the response if you had a separate membership model
    });

    if (!workspace) {
      return res.status(404).json({ message: 'Invalid or expired invite link.' });
    }

    res.status(200).json({
      message: 'Workspace found.',
      workspaceId: workspace.id,
      workspaceName: workspace.name,
      inviteLink: workspace.inviteLink,
      // You could add a list of members here if you had a many-to-many relationship
    });
  } catch (error) {
    console.error('Error joining workspace:', error);
    res.status(500).json({ message: 'Failed to join workspace.', error: (error as Error).message });
  }
});


// @route   GET /api/workspaces/:workspaceId/documents
// @desc    Gets all documents associated with a specific workspace
router.get('/:workspaceId/documents', async (req: Request, res: Response) => {
  const { workspaceId } = req.params;

  try {
    // Find all documents in MongoDB that have this workspaceId
    const documents = await DocumentModel.find({ workspaceId: workspaceId });

    res.status(200).json({
      message: `Found ${documents.length} documents for workspace ${workspaceId}.`,
      documents: documents,
    });
  } catch (error) {
    console.error('Error getting workspace documents:', error);
    res.status(500).json({ message: 'Failed to retrieve documents.', error: (error as Error).message });
  }
});

export default router;
