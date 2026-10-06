export const accessState={csrf:''}
export const csrfHeaders=():Record<string,string>=>accessState.csrf?{'X-EDY-CSRF':accessState.csrf}:{}
