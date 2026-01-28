#!/usr/bin/env node

/**
 * GCash Configuration Setup Script
 * Helps configure GCash integration for the Boarding House System
 */

const fs = require('fs');
const path = require('path');
const readline = require('readline');

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout
});

const envFilePath = path.join(__dirname, '.env');
const examplePath = path.join(__dirname, '.env.example');

function question(prompt) {
  return new Promise((resolve) => {
    rl.question(prompt, resolve);
  });
}

async function setupGCash() {
  console.log('\n═══════════════════════════════════════════════════════════');
  console.log('  GCash Payment Integration Setup');
  console.log('═══════════════════════════════════════════════════════════\n');

  // Check if .env exists
  const envExists = fs.existsSync(envFilePath);
  
  if (envExists) {
    const overwrite = await question('❓ .env file already exists. Overwrite? (y/n): ');
    if (overwrite.toLowerCase() !== 'y') {
      console.log('\n✗ Setup cancelled.');
      rl.close();
      return;
    }
  }

  console.log('\n📝 Please enter your GCash merchant credentials:');
  console.log('   (Get these from: https://merchant.gcash.com/account/keys)\n');

  const apiKey = await question('🔑 GCash API Key: ');
  const secretKey = await question('🔐 GCash Secret Key: ');
  const merchantId = await question('🏪 Merchant ID: ');
  
  const environment = await question('\n🌍 Environment? (sandbox/production) [sandbox]: ');
  const env = environment.toLowerCase() === 'production' ? 'production' : 'sandbox';
  
  const apiEndpoint = env === 'production' 
    ? 'https://api.gcash.com/v1'
    : 'https://sandbox-api.gcash.com/v1';

  const webhookSecret = await question('🔔 Webhook Secret: ');
  const frontendUrl = await question('🌐 Frontend URL [http://localhost:5173]: ') || 'http://localhost:5173';
  const backendUrl = await question('🖥️  Backend URL [http://localhost:5000]: ') || 'http://localhost:5000';

  // Create .env content
  const envContent = `# GCash Configuration
GCASH_API_KEY=${apiKey}
GCASH_SECRET_KEY=${secretKey}
GCASH_MERCHANT_ID=${merchantId}
GCASH_API_ENDPOINT=${apiEndpoint}
GCASH_WEBHOOK_SECRET=${webhookSecret}

# Application URLs
FRONTEND_URL=${frontendUrl}
BACKEND_URL=${backendUrl}

# Server Configuration
PORT=5000
NODE_ENV=${env === 'production' ? 'production' : 'development'}
`;

  // Write .env file
  fs.writeFileSync(envFilePath, envContent);
  
  console.log('\n✅ Configuration saved to .env\n');
  
  // Display webhook setup instructions
  console.log('═══════════════════════════════════════════════════════════');
  console.log('  Next Steps - Configure Webhook in GCash Dashboard');
  console.log('═══════════════════════════════════════════════════════════\n');
  
  console.log('1. Go to GCash Merchant Dashboard:');
  console.log('   https://merchant.gcash.com/dashboard\n');
  
  console.log('2. Navigate to Settings → Webhooks\n');
  
  console.log('3. Add a new webhook with these details:');
  console.log(`   URL: ${backendUrl}/api/webhooks/gcash`);
  console.log('   Events: payment.completed, payment.failed, payment.cancelled\n');
  
  console.log('4. For local testing with ngrok:');
  console.log('   • Install ngrok: https://ngrok.com/download');
  console.log('   • Run: ngrok http 5000');
  console.log('   • Use the HTTPS URL provided by ngrok as your webhook URL\n');
  
  if (env === 'sandbox') {
    console.log('💡 You\'re using SANDBOX mode for testing.\n');
    console.log('   Test Payment Flow:');
    console.log('   • Make sure you have test merchant credentials');
    console.log('   • Use sandbox GCash numbers for testing');
    console.log('   • Check GCash Sandbox Dashboard for test webhooks\n');
  } else {
    console.log('⚠️  You\'re using PRODUCTION mode.\n');
    console.log('   IMPORTANT:');
    console.log('   • Ensure you have production merchant credentials');
    console.log('   • Use HTTPS for all endpoints');
    console.log('   • Test thoroughly before going live\n');
  }

  console.log('5. Restart your application:');
  console.log('   npm run dev\n');

  console.log('📖 For detailed documentation:');
  console.log('   See GCASH_INTEGRATION.md in the project root\n');

  console.log('═══════════════════════════════════════════════════════════\n');
  
  rl.close();
}

// Run setup
setupGCash().catch((error) => {
  console.error('❌ Setup error:', error.message);
  rl.close();
  process.exit(1);
});
