import { DataTypes,Model,Optional } from "sequelize";
import { sequelize } from "../config/mysql";

//user interface
interface UserAttributes{
    id:string;
    email:string;
    passwordHash:string;
    username:string;
    createdAt?:Date;
    updatedAt?:Date;
}

interface UserCreationAttributes extends Optional<UserAttributes,'id' | 'createdAt' | 'updatedAt'>{}

// Define the User model class
class User extends Model<UserAttributes, UserCreationAttributes> implements UserAttributes {
  public id!: string;
  public email!: string;
  public passwordHash!: string;
  public username!: string;

  // Timestamps
  public readonly createdAt!: Date;
  public readonly updatedAt!: Date;
}

// Define the User model
User.init(
    {
        id:{
            type:DataTypes.UUID,
            defaultValue:DataTypes.UUIDV4,
            primaryKey:true,
        },
        email:{
            type:DataTypes.STRING(255),
            allowNull:false,
            unique:true,
            validate:{
                isEmail:true,
            }
        },
        passwordHash:{
            type:DataTypes.STRING(255),
            allowNull:false,
        },
        username:{
            type:DataTypes.STRING(100),
            allowNull:false,
            unique:true,
        },
    },
    {
        sequelize,
        tableName:'user',
        timestamps:true,
    }
);

export default User;