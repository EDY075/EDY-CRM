import {createContext,useContext} from 'react'
export interface Actor{id:string;nome:string;papel:string;workspace:string;modo:string}
export interface Access{ator:Actor|null;workspaces:{id:string;nome:string;papel:string}[];csrf:string;login_necessario:boolean}
export const ActorContext=createContext<Access|null>(null)
export const useAccess=()=>useContext(ActorContext)
