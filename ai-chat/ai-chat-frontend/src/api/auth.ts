// src/api/auth.ts
import request from './request';

export const loginApi = (data: { username: string; password: string }) => {
  return request.post('/auth/login', data);
};

export const registerApi = (data: { username: string; password: string }) => {
  return request.post('/auth/register', data);
};
