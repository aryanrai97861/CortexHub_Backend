import {Sequelize} from 'sequelize';
import dotenv from 'dotenv';
dotenv.config();

const sequelize=new Sequelize(
    process.env.MYSQL_DATABASE as string,
    process.env.MYSQL_USER as string,
    process.env.MYSQL_PASSWORD as string,
    {
        host:process.env.MYSQL_HOST as string,
        port:parseInt(process.env.MYSQL_PORT as string,10) || 3306,
        dialect:'mysql',
        logging:false,
        define:{
            timestamps:true,
        },
        pool:{
            max:5,
            min:0,
            acquire:30000,
            idle:10000,
        },
    }
);

const connectMySQL=async():Promise<void>=>{
    try{
        await sequelize.authenticate();
        console.log('MySQL connection has been established successfully.');
    }catch(error){
        console.error('Unable to connect to the database:',error);
        process.exit(1);
    }
};

export {sequelize,connectMySQL};