import mongoose from "mongoose";

const connectDB=async():Promise<void>=>{
    try{
        const mongoUri=process.env.MONGO_URI;

        if(!mongoUri){
            throw new Error('MONGODB_URI is not defined in .env file');
        }

        await mongoose.connect(mongoUri);
        console.log('Connected to MongoDB');
    }catch(error:any){
        console.error('Error connecting to MongoDB:',error.message);
        process.exit(1);
    }
};

export default connectDB;