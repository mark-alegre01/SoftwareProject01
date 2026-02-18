const fs = require('fs');
const html = fs.readFileSync('templates/core/devices.html','utf8');
let scripts = '';
for (const m of html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/gi)) {
  scripts += m[1] + '\n';
}
for (const m of html.matchAll(/onclick\s*=\s*"([^"]*)"/gi)) {
  scripts += m[1] + '\n';
}
try{
  new Function(scripts);
  console.log('No syntax errors found by new Function');
}catch(e){
  console.error('SyntaxError:', e.message);
  console.error(e.stack);
  // write the problematic script to a file for inspection
  fs.writeFileSync('tmp_extracted_script.js', scripts);
  console.log('Wrote tmp_extracted_script.js for inspection');
}
