import { FlatCompat } from "@eslint/eslintrc";
const compat = new FlatCompat({ baseDirectory: import.meta.dirname });
const config = [{ ignores: [".next/**", "node_modules/**", ".pytest_cache/**"] }, ...compat.extends("next/core-web-vitals")];
export default config;
