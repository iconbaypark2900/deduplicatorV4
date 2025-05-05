# Tailwind CSS setup

This frontend uses TailwindCSS 3.x.

## First-time install
```
npm install
npx tailwindcss init -p
```
This creates `tailwind.config.js` and `postcss.config.js` automatically.

## Content paths
Update `tailwind.config.js` to include:
```js
content: [
  './app/**/*.{js,ts,jsx,tsx}',
  './components/**/*.{js,ts,jsx,tsx}',
  './pages/**/*.{js,ts,jsx,tsx}',
]
``` 