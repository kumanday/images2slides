FROM node:20-alpine

WORKDIR /app

COPY saas/web/package.json ./package.json
COPY saas/web/tsconfig.json ./tsconfig.json
COPY saas/web/next.config.js ./next.config.js
COPY saas/web/postcss.config.js ./postcss.config.js
COPY saas/web/tailwind.config.js ./tailwind.config.js
COPY saas/web/next-env.d.ts ./next-env.d.ts
COPY saas/web/app ./app
COPY saas/web/lib ./lib

RUN npm install

EXPOSE 3000

CMD ["npm", "run", "dev", "--", "-p", "3000"]
