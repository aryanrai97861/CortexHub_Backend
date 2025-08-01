// backend/src/models/mysql/Workspace.ts

import { DataTypes, Model, Optional } from 'sequelize';
import { sequelize } from '../config/mysql';
import User from '../models/User'; // Import the User model for associations

// Define the interface for Workspace attributes
interface WorkspaceAttributes {
  id: string; // UUID
  name: string;
  ownerId: string; // Foreign key to User
  inviteLink: string; // Generated link for joining
  description?: string;
  createdAt?: Date;
  updatedAt?: Date;
}

// Some attributes are optional in .build and .create calls
interface WorkspaceCreationAttributes extends Optional<WorkspaceAttributes, 'id' | 'createdAt' | 'updatedAt' | 'description'> {}

// Define the Workspace model class
class Workspace extends Model<WorkspaceAttributes, WorkspaceCreationAttributes> implements WorkspaceAttributes {
  declare id: string;
  declare name: string;
  declare ownerId: string;
  declare inviteLink: string;
  declare description?: string;

  // Timestamps
  declare readonly createdAt: Date;
  declare readonly updatedAt: Date;
}

// Initialize the Workspace model
Workspace.init(
  {
    id: {
      type: DataTypes.UUID,
      defaultValue: DataTypes.UUIDV4,
      primaryKey: true,
    },
    name: {
      type: DataTypes.STRING(255),
      allowNull: false,
    },
    ownerId: {
      type: DataTypes.UUID,
      allowNull: false,
      references: {
        model: User, // Reference the User model
        key: 'id',
      },
    },
    inviteLink: {
      type: DataTypes.STRING(255),
      allowNull: false,
      unique: true,
    },
    description: {
      type: DataTypes.TEXT,
      allowNull: true,
    },
  },
  {
    sequelize,
    tableName: 'workspaces',
    timestamps: true,
  }
);

// Define associations
// A User can own many Workspaces
User.hasMany(Workspace, {
  foreignKey: 'ownerId',
  as: 'ownedWorkspaces',
  onDelete: 'CASCADE', // If a user is deleted, delete their workspaces
});

// A Workspace belongs to one User (owner)
Workspace.belongsTo(User, {
  foreignKey: 'ownerId',
  as: 'owner',
});

export default Workspace;
