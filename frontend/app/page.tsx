'use client';

import { useState } from 'react';
import axios from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Payment {
  payment_id: string;
  status: string;
  redirect_url?: string;
  amount: string;
  currency: string;
}

export default function Home() {
  const [loading, setLoading] = useState(false);
  const [payment, setPayment] = useState<Payment | null>(null);
  const [error, setError] = useState<string | null>(null);

  const createPayment = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await axios.post(`${API_URL}/payments`, {
        amount: '50000',
        currency: 'COP',
        payment_method: 'PSE',
        bank: 'banco_azul',
        customer: {
          email: 'demo@example.com',
          name: 'Juan Demo',
          document: '1234567890'
        },
        redirect_url: `${window.location.origin}/return`,
        idempotency_key: crypto.randomUUID()
      });

      const paymentData = response.data;
      setPayment(paymentData);

      // Simulate redirect to bank
      if (paymentData.redirect_url) {
        alert(`Redirecting to bank: ${paymentData.redirect_url}\n\n(In real app, you'd be redirected to Banco Azul)`);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create payment');
    } finally {
      setLoading(false);
    }
  };

  const simulateWebhook = async (status: 'approved' | 'declined') => {
    if (!payment) return;

    try {
      await axios.post(`${API_URL}/webhooks`, {
        payment_id: payment.payment_id,
        status: status,
        timestamp: new Date().toISOString(),
        signature: 'mock_signature'
      });

      // Refresh payment status
      const response = await axios.get(`${API_URL}/payments/${payment.payment_id}`);
      setPayment(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to send webhook');
    }
  };

  return (
    <main className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-8">
      <div className="max-w-4xl mx-auto">
        <div className="bg-white rounded-lg shadow-xl p-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">
            Banco Azul E2E Demo
          </h1>
          <p className="text-gray-600 mb-8">
            Test async payment flows with webhook simulation
          </p>

          <div className="mb-8">
            <button
              onClick={createPayment}
              disabled={loading}
              className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-semibold py-3 px-6 rounded-lg transition-colors"
            >
              {loading ? 'Creating Payment...' : 'Create PSE Payment'}
            </button>
          </div>

          {error && (
            <div className="mb-8 p-4 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-red-800 font-medium">Error: {error}</p>
            </div>
          )}

          {payment && (
            <div className="space-y-6">
              <div className="bg-gray-50 rounded-lg p-6">
                <h2 className="text-2xl font-semibold mb-4">Payment Created</h2>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <span className="text-gray-600">Payment ID:</span>
                    <p className="font-mono text-sm">{payment.payment_id}</p>
                  </div>
                  <div>
                    <span className="text-gray-600">Status:</span>
                    <p className="font-semibold">
                      <span className={`inline-block px-3 py-1 rounded-full text-sm ${
                        payment.status === 'approved' ? 'bg-green-100 text-green-800' :
                        payment.status === 'declined' ? 'bg-red-100 text-red-800' :
                        payment.status === 'pending' ? 'bg-yellow-100 text-yellow-800' :
                        'bg-gray-100 text-gray-800'
                      }`}>
                        {payment.status.toUpperCase()}
                      </span>
                    </p>
                  </div>
                  <div>
                    <span className="text-gray-600">Amount:</span>
                    <p className="font-semibold">{payment.currency} {parseInt(payment.amount).toLocaleString()}</p>
                  </div>
                  <div>
                    <span className="text-gray-600">Currency:</span>
                    <p className="font-semibold">{payment.currency}</p>
                  </div>
                </div>
              </div>

              {payment.status === 'pending' && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
                  <h3 className="text-xl font-semibold mb-4">Simulate Webhook</h3>
                  <p className="text-gray-600 mb-4">
                    In production, the bank would send a webhook. Simulate one here:
                  </p>
                  <div className="flex gap-4">
                    <button
                      onClick={() => simulateWebhook('approved')}
                      className="bg-green-600 hover:bg-green-700 text-white font-semibold py-2 px-4 rounded-lg transition-colors"
                    >
                      ✓ Approve Payment
                    </button>
                    <button
                      onClick={() => simulateWebhook('declined')}
                      className="bg-red-600 hover:bg-red-700 text-white font-semibold py-2 px-4 rounded-lg transition-colors"
                    >
                      ✗ Decline Payment
                    </button>
                  </div>
                </div>
              )}

              {payment.status === 'approved' && (
                <div className="bg-green-50 border border-green-200 rounded-lg p-6">
                  <h3 className="text-xl font-semibold text-green-800">✓ Payment Successful!</h3>
                  <p className="text-green-700 mt-2">
                    The payment has been approved. In a real app, the order would be fulfilled.
                  </p>
                </div>
              )}

              {payment.status === 'declined' && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-6">
                  <h3 className="text-xl font-semibold text-red-800">✗ Payment Declined</h3>
                  <p className="text-red-700 mt-2">
                    The payment was declined by the bank. Please try again or use a different payment method.
                  </p>
                </div>
              )}
            </div>
          )}

          <div className="mt-12 pt-8 border-t border-gray-200">
            <h3 className="text-lg font-semibold mb-4">About This Demo</h3>
            <ul className="space-y-2 text-gray-600">
              <li>• Tests async payment flows (PSE, PIX, OXXO)</li>
              <li>• Simulates webhook timing issues and race conditions</li>
              <li>• Validates idempotency and duplicate webhook handling</li>
              <li>• Backed by comprehensive E2E test suite (11 tests)</li>
            </ul>
            <div className="mt-4">
              <a
                href="https://github.com/yourusername/banco-azul-e2e"
                className="text-blue-600 hover:text-blue-800 font-medium"
                target="_blank"
                rel="noopener noreferrer"
              >
                View Source Code →
              </a>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
