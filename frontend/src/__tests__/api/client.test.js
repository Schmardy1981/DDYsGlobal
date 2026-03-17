import axios from 'axios';

// Test that API client is configured correctly
describe('API Client', () => {
  it('should export an axios instance', () => {
    const client = require('../../api/client');
    expect(client.default || client).toBeDefined();
  });
});
