import js from "@eslint/js";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["**/node_modules/**", "cdk.out/**", ".venv/**", "**/dist/**", "**/coverage/**"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    languageOptions: {
      globals: {
        console: "readonly", process: "readonly", module: "readonly", require: "readonly",
        __dirname: "readonly", exports: "readonly", Buffer: "readonly",
        describe: "readonly", test: "readonly", expect: "readonly", jest: "readonly",
      },
    },
  },
  {
    files: ["**/*.cjs"],
    rules: { "@typescript-eslint/no-require-imports": "off" },
  },
);
