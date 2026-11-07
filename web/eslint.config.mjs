import next from "eslint-config-next";

const config = [...next, { ignores: [".next/**", "out/**", "public/**", "playwright-report/**"] }];

export default config;
