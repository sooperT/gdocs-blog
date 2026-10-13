import Anthropic from '@anthropic-ai/sdk';
import pg from 'pg';
import { readFileSync, existsSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import { embedQuery, matchSections, prepareQuerySteps, QUESTION_MATCH_THRESHOLD, TOP_K } from './lib/retrieval.js';
import { track, cleanPosthogId, retrievalSpanEvent, generationEvent } from './lib/analytics.js';

// Load .env in development
const currentFilePath = fileURLToPath(import.meta.url);
const currentDirPath = dirname(currentFilePath);
const envPath = join(currentDirPath, '../../.env');
if (existsSync(envPath)) {
  const envContent = readFileSync(envPath, 'utf-8');
  envContent.split('\n').forEach(line => {
    const [key, ...valueParts] = line.split('=');
    if (key && valueParts.length > 0) {
      process.env[key.trim()] = valueParts.join('=').trim();
    }
  });
}

// Load system prompt from file
const SYSTEM_PROMPT = readFileSync(join(currentDirPath, 'system-prompt.md'), 'utf-8');

const anthropic = new Anthropic();
const CHAT_MODEL = 'claude-sonnet-5';
const CHAT_MAX_TOKENS = 1024;

// Database connection
const pool = new pg.Pool({
  connectionString: process.env.NILEDB_URL,
  ssl: { rejectUnauthorized: false }
});

// Log deflection to dedicated table for review
async function logDeflection(query, topMatch, topScore, sessionId) {
  try {
    await pool.query(`
      INSERT INTO deflections (query, top_match, top_score, session_id)
      VALUES ($1, $2, $3, $4)
    `, [query, topMatch, topScore, sessionId]);
  } catch (error) {
    console.error('Failed to log deflection:', error);
  }
}

// Log chat session to database
async function logChatExchange(sessionId, userMessage, assistantResponse, retrievalInfo) {
  try {
    const messageEntry = {
      timestamp: new Date().toISOString(),
      user: userMessage,
      assistant: assistantResponse,
    };
    const retrievalEntry = {
      timestamp: new Date().toISOString(),
      query: userMessage,
      matches: retrievalInfo,
    };

    // Upsert: create session if new, append if exists
    await pool.query(`
      INSERT INTO chat_logs (session_id, messages, retrieval_log)
      VALUES ($1, $2::jsonb, $3::jsonb)
      ON CONFLICT (session_id) DO UPDATE SET
        messages = chat_logs.messages || $2::jsonb,
        retrieval_log = chat_logs.retrieval_log || $3::jsonb,
        updated_at = NOW()
    `, [sessionId, JSON.stringify([messageEntry]), JSON.stringify([retrievalEntry])]);
  } catch (error) {
    console.error('Failed to log chat:', error);
    // Don't throw - logging failures shouldn't break chat
  }
}

// Log an error to dedicated table for review (fire-and-forget)
async function logError(sessionId, query, errorMessage) {
  try {
    await pool.query(`
      INSERT INTO error_logs (session_id, query, error)
      VALUES ($1, $2, $3)
    `, [sessionId, query, errorMessage]);
  } catch (error) {
    console.error('Failed to log error:', error);
    // Don't throw - logging failures shouldn't break chat
  }
}

// Exported for scripts/eval-routing.js — keeps the eval on the exact production path
export async function retrieveContent(query) {
  // Steps 1-4: shared query clean-up (lib/retrieval.js): normalize third-person
  // to first-person, expand contractions, aliases, then synonyms (LSI-lite)
  const steps = await prepareQuerySteps(query, { sql: pool });
  const normalizedQuery = steps.normalized;
  const contractionsExpanded = steps.contractions;
  const aliasExpanded = steps.aliases;
  const synonymExpanded = steps.synonyms;

  if (normalizedQuery !== query) {
    console.log('[RAG] Normalized:', query, '->', normalizedQuery);
  }
  if (contractionsExpanded !== normalizedQuery) {
    console.log('[RAG] Contractions expanded:', normalizedQuery, '->', contractionsExpanded);
  }
  if (aliasExpanded !== contractionsExpanded) {
    console.log('[RAG] Aliases expanded:', contractionsExpanded, '->', aliasExpanded);
  }
  if (synonymExpanded !== aliasExpanded) {
    console.log('[RAG] Synonyms expanded:', aliasExpanded, '->', synonymExpanded);
  }

  console.log('[RAG] Final query:', synonymExpanded);

  // Step 5: Get embedding
  const embedding = await embedQuery(synonymExpanded);
  if (!embedding) {
    console.log('[RAG] Failed to get embedding');
    return { chunks: [], method: 'none' };
  }

  // Step 3: Primary search - match against question embeddings
  const questionMatches = await matchSections(embedding, { topK: TOP_K, sql: pool });
  console.log('[RAG] Question matches:', questionMatches.length);
  if (questionMatches.length > 0) {
    console.log('[RAG] Top question match:', questionMatches[0].title,
                'question:', questionMatches[0].question_text?.substring(0, 40),
                'similarity:', questionMatches[0].similarity?.toFixed(3));
  }

  // Step 4: Check if we have a good question match
  const goodQuestionMatches = questionMatches.filter(r => r.similarity >= QUESTION_MATCH_THRESHOLD);

  if (goodQuestionMatches.length > 0) {
    console.log('[RAG] Using', goodQuestionMatches.length, 'question matches above threshold');
    return { chunks: goodQuestionMatches, method: 'question', topMatch: null };
  }

  // No match — bot will deflect gracefully
  // Include top match info for logging (even though it's below threshold)
  const topMatch = questionMatches[0] || null;
  console.log('[RAG] No good question match, will deflect');
  return {
    chunks: [],
    method: 'none',
    topMatch: topMatch ? { title: topMatch.title, score: topMatch.similarity } : null
  };
}

// Format retrieved chunks for the prompt
function formatRetrievedContent(chunks) {
  if (!chunks || chunks.length === 0) return '';

  const formatted = chunks.map(chunk => {
    let header = `[${chunk.chunk_type}]`;
    if (chunk.company_name) {
      header += ` ${chunk.company_name}`;
      if (chunk.years_start) {
        header += ` (${chunk.years_start}-${chunk.years_end || 'present'})`;
      }
    }
    return `${header}\n${chunk.content}`;
  }).join('\n\n---\n\n');

  return `\n\n<retrieved_content>\n${formatted}\n</retrieved_content>\n\nUse the retrieved content above to inform your response. This is grounded information about Tom's experience. If the answer isn't in the retrieved content or the system prompt, acknowledge that you don't have that information and suggest emailing Tom directly.`;
}

export default async (request, context) => {
  // Handle CORS preflight
  if (request.method === 'OPTIONS') {
    return new Response(null, {
      status: 204,
      headers: {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type',
      },
    });
  }

  // Only allow POST
  if (request.method !== 'POST') {
    return new Response(JSON.stringify({ error: 'Method not allowed' }), {
      status: 405,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  // Declared outside try so the outer catch can log with context
  let chatSessionId = null;
  let lastUserQuery = null;

  try {
    const { messages, sessionId, phId, phSession } = await request.json();

    // Validate messages
    if (!messages || !Array.isArray(messages) || messages.length === 0) {
      return new Response(JSON.stringify({ error: 'Messages array required' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    // Generate session ID if not provided
    chatSessionId = sessionId || `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

    // PostHog LLM analytics (lib/analytics.js): one trace per turn, grouped by
    // the chat session; a no-op without POSTHOG_KEY.
    const traceId = `${chatSessionId}_${Date.now()}`;
    const phOpts = { request, context, distinctId: cleanPosthogId(phId) || chatSessionId };
    const phIds = { traceId, sessionId: chatSessionId, webSessionId: phSession };

    // Cap conversation history to prevent token overflow
    const MAX_MESSAGES = 20;
    const trimmedMessages = messages.slice(-MAX_MESSAGES);

    // Get the latest user message for RAG search
    const lastUserMessage = trimmedMessages.filter(m => m.role === 'user').pop();
    lastUserQuery = lastUserMessage?.content || null;
    let ragContext = '';
    let followUps = [];
    let retrievalInfo = { method: 'none', matches: [] };

    if (lastUserMessage) {
      const retrievalStart = Date.now();
      const { chunks, method, topMatch } = await retrieveContent(lastUserMessage.content);
      const retrievalMs = Date.now() - retrievalStart;

      // No match found — return hardcoded deflect, skip Claude entirely
      if (method === 'none') {
        const deflectMessage = "I don't have specific information about that in my knowledge base. Try asking about my work experience, skills, or background — or rephrase your question.";

        // Log deflection to dedicated table for review (awaited — Netlify
        // freezes the invocation once the response closes, killing in-flight writes)
        await logDeflection(
          lastUserMessage.content,
          topMatch?.title || null,
          topMatch?.score || null,
          chatSessionId
        );

        // Also log to chat logs
        await logChatExchange(chatSessionId, lastUserMessage.content, deflectMessage, { method: 'none', matches: [] });
        await track('$ai_span', { ...phOpts, properties: retrievalSpanEvent({
          ...phIds, query: lastUserMessage.content, retrieval: { method, matches: [], topMatch }, latencyMs: retrievalMs,
        }) });

        // Return deflect as streaming response (for consistent client handling)
        const deflectFollowUps = [
          'What can I ask you?',
          'Tell me about yourself',
          'What are you looking for?',
        ];

        const encoder = new TextEncoder();
        const deflectStream = new ReadableStream({
          start(controller) {
            controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: 'delta', text: deflectMessage })}\n\n`));
            controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: 'follow_ups', suggestions: deflectFollowUps })}\n\n`));
            controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: 'done', sessionId: chatSessionId })}\n\n`));
            controller.close();
          }
        });

        return new Response(deflectStream, {
          headers: {
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*',
          },
        });
      }

      ragContext = formatRetrievedContent(chunks);
      // Extract follow-ups for clickable chips (sent as structured SSE data).
      // Chip count is content-driven (most sections define 3); cap is a safety net.
      followUps = (chunks[0]?.follow_ups || []).slice(0, 8);
      // Capture retrieval info for logging
      retrievalInfo = {
        method,
        matches: chunks.map(c => ({
          section: c.title,
          score: c.similarity?.toFixed(3),
        })),
      };
      await track('$ai_span', { ...phOpts, properties: retrievalSpanEvent({
        ...phIds, query: lastUserMessage.content, retrieval: retrievalInfo, latencyMs: retrievalMs,
      }) });
    }

    // Combine system prompt with RAG context
    const enhancedSystemPrompt = SYSTEM_PROMPT + ragContext;

    // Create streaming response
    const generationStart = Date.now();
    let firstTokenMs = null;
    const stream = await anthropic.messages.stream({
      model: CHAT_MODEL,
      max_tokens: CHAT_MAX_TOKENS,
      thinking: { type: 'disabled' },
      system: enhancedSystemPrompt,
      messages: trimmedMessages,
    });

    // Collect full response for logging
    let fullResponse = '';
    const trackGeneration = async (error) => {
      let usage = null;
      if (!error) { try { usage = (await stream.finalMessage()).usage; } catch { /* usage stays null */ } }
      await track('$ai_generation', { ...phOpts, properties: generationEvent({
        ...phIds, retrieval: retrievalInfo, model: CHAT_MODEL, maxTokens: CHAT_MAX_TOKENS,
        system: enhancedSystemPrompt, messages: trimmedMessages, output: fullResponse, usage,
        latencyMs: Date.now() - generationStart, firstTokenMs, error,
      }) });
    };

    // Set up streaming response
    const encoder = new TextEncoder();
    const readableStream = new ReadableStream({
      async start(controller) {
        try {
          for await (const event of stream) {
            if (event.type === 'content_block_delta' && event.delta.type === 'text_delta') {
              if (firstTokenMs === null) firstTokenMs = Date.now() - generationStart;
              fullResponse += event.delta.text;
              const data = JSON.stringify({ type: 'delta', text: event.delta.text });
              controller.enqueue(encoder.encode(`data: ${data}\n\n`));
            }
          }
          // Log the complete exchange after streaming finishes
          if (lastUserMessage) {
            await logChatExchange(chatSessionId, lastUserMessage.content, fullResponse, retrievalInfo);
          }
          await trackGeneration(null);
          // Send follow-up suggestions as structured data for clickable chips
          if (followUps.length > 0) {
            controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: 'follow_ups', suggestions: followUps })}\n\n`));
          }
          controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: 'done', sessionId: chatSessionId })}\n\n`));
          controller.close();
        } catch (error) {
          console.error('Streaming error:', error);
          logError(chatSessionId, lastUserMessage?.content || null, error.message);
          await trackGeneration(error.message);
          controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: 'error', message: error.message })}\n\n`));
          controller.close();
        }
      },
    });

    return new Response(readableStream, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Access-Control-Allow-Origin': '*',
      },
    });

  } catch (error) {
    console.error('Chat error:', error);
    logError(chatSessionId, lastUserQuery, error.message);

    // User-friendly error messages based on error type
    let userMessage = 'Something went wrong. Please try again.';

    if (error.message?.includes('authentication') || error.message?.includes('apiKey') || error.message?.includes('API key')) {
      userMessage = 'TomBot is having trouble connecting to its brain. Please try again later.';
    } else if (error.message?.includes('rate') || error.status === 429) {
      userMessage = 'TomBot is a bit overwhelmed right now. Please wait a moment and try again.';
    } else if (error.message?.includes('timeout') || error.code === 'ETIMEDOUT') {
      userMessage = 'TomBot took too long to respond. Please try again.';
    } else if (error.message?.includes('database') || error.message?.includes('connection')) {
      userMessage = 'TomBot is having trouble accessing its memory. Please try again later.';
    }

    return new Response(JSON.stringify({ error: userMessage }), {
      status: 500,
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
      },
    });
  }
};

export const config = {
  path: '/api/chat',
};
