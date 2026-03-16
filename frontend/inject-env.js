/**
 * inject-env.js
 * Netlify build step: replaces REPLACE_API_URL and REPLACE_EVAL_KEY
 * placeholders in index.html with actual environment variable values.
 *
 * Set in Netlify dashboard → Site settings → Environment variables:
 *   API_BASE_URL  =  https://your-app.onrender.com
 *   EVAL_API_KEY  =  (your secret key, or leave blank)
 */
const fs  = require('fs');
const path = require('path');

const indexPath = path.join(__dirname, 'index.html');
let html = fs.readFileSync(indexPath, 'utf8');

const apiUrl  = process.env.API_BASE_URL  || 'http://localhost:5000';
const apiKey  = process.env.EVAL_API_KEY  || '';

html = html
  .replace(/REPLACE_API_URL/g, apiUrl)
  .replace(/REPLACE_EVAL_KEY/g, apiKey);

fs.writeFileSync(indexPath, html);
console.log('inject-env: API_BASE_URL =', apiUrl);
console.log('inject-env: EVAL_API_KEY =', apiKey ? '(set)' : '(not set)');