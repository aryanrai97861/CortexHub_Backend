import {DataTypes,Model,Optional} from 'sequelize';
import { sequelize } from '../config/mysql';
import User from './User';
import Workspace from './Workspace';

interface TaskAttributes {
  id: string; // UUID
  title: string;
  description?: string;
  status: "todo" | "in-progress" | "done";
  priority: "low" | "medium" | "high";
  assignedToId?: string; // Foreign key to User
  workspaceId: string; // Foreign key to Workspace
  createdAt?: Date;
  updatedAt?: Date;
}

// Some attributes are optional in .build and .create calls
interface TaskCreationAttributes extends Optional<TaskAttributes, 'id' | 'createdAt' | 'updatedAt'> {}

// Define the task model class
class Task extends Model<TaskAttributes, TaskCreationAttributes> implements TaskAttributes {
  declare id: string;
  declare title: string;
  declare description?: string;
  declare status: 'todo' | 'in-progress' | 'done';
  declare priority: 'low' | 'medium' | 'high';
  declare assignedToId?: string;
  declare workspaceId: string;

  // Timestamps
  declare readonly createdAt: Date;
  declare readonly updatedAt: Date;
}

// Initialize the task model
Task.init(
  {
    id: {
      type: DataTypes.UUID,
      defaultValue: DataTypes.UUIDV4,
      primaryKey: true,
    },
    title: {
      type: DataTypes.STRING(255),
      allowNull: false,
    },
    description: {
      type: DataTypes.TEXT,
      allowNull: true,
    },
    status: {
      type: DataTypes.ENUM('todo', 'in-progress', 'done'),
      defaultValue: 'todo',
      allowNull: false,
    },
    priority: {
      type: DataTypes.ENUM('low', 'medium', 'high'),
      defaultValue: 'medium',
      allowNull: false,
    },
    assignedToId: {
      type: DataTypes.UUID,
      allowNull: true,
      references: {
        model: User,
        key: 'id',
      },
    },
    workspaceId: {
      type: DataTypes.UUID,
      allowNull: false,
      references: {
        model: Workspace,
        key: 'id',
      },
    },
  },
  {
    sequelize,
    tableName: 'tasks',
    timestamps: true,
  }
);

// Define associations
Task.belongsTo(User, {
  foreignKey: 'assignedToId',
  as: 'assignedTo',
});

Task.belongsTo(Workspace, {
  foreignKey: 'workspaceId',
  as: 'workspace',
});

export default Task;
