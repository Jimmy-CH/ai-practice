import { api } from './client'

export interface Project { id: string; name: string; theme: string; audience: string; tone: string }
export type ProjectInput = Omit<Project, 'id'>

export const listProjects = async () => (await api.get<Project[]>('/projects')).data
export const createProject = async (input: ProjectInput) => (await api.post<Project>('/projects', input)).data
