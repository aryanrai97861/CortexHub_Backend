import mongoose,{Document,Schema} from "mongoose";

// Define the interface for a Document document
export interface IDocument extends Document{
    fileName:string,
    originalType:string,
    uploadedAt:Date;
    processed:boolean;
    chromaDocumentId?:string;
    workspaceId:string;
}

//define the moongose schema for the document
const DocumentSchema:Schema=new Schema({
    fileName:{type:String,required:true},
    originalType:{type:String,required:true},
    uploadedAt:{type:Date,default:Date.now},
    processed:{type:Boolean,default:false},
    chromaDocumentId:{type:String,unique:true,sparse:true},
    workspaceId:{type:String,required:true},
});

const DocumentModel=mongoose.model<IDocument>('Document',DocumentSchema);

export default DocumentModel;