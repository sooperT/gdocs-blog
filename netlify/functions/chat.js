import Anthropic from '@anthropic-ai/sdk';
import pg from 'pg';
import { readFileSync, existsSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

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

// Database connection
const pool = new pg.Pool({
  connectionString: process.env.NILEDB_URL,
  ssl: { rejectUnauthorized: false }
});

// Get embedding from Voyage AI with retry
async function getEmbedding(text, retries = 2) {
  for (let attempt = 0; attempt <= retries; attempt++) {
    const response = await fetch('https://api.voyageai.com/v1/embeddings', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${process.env.VOYAGE_API_KEY}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        input: [text],
        model: 'voyage-3'
      })
    });

    if (response.ok) {
      const data = await response.json();
      return data.data[0].embedding;
    }

    if (response.status === 429 && attempt < retries) {
      await new Promise(r => setTimeout(r, 1000 * (attempt + 1)));
      continue;
    }

    console.error('Voyage API error:', await response.text());
    return null;
  }
  return null;
}

// Expand aliases in query (e.g., "Novo" -> "Novo Nordisk")
async function expandAliases(query) {
  try {
    // Sort by alias length descending to avoid partial replacements
    const result = await pool.query('SELECT alias, canonical_name FROM aliases ORDER BY LENGTH(alias) DESC');
    let expanded = query;
    for (const row of result.rows) {
      // Only replace if the canonical name isn't already present
      if (!expanded.toLowerCase().includes(row.canonical_name.toLowerCase())) {
        const regex = new RegExp(`\\b${row.alias}\\b`, 'gi');
        expanded = expanded.replace(regex, row.canonical_name);
      }
    }
    return expanded;
  } catch (error) {
    console.error('Alias expansion error:', error);
    return query;
  }
}

// Primary search: match user query against question embeddings
// This finds the best matching pre-defined question variations
async function searchByQuestionMatch(embedding, limit = 5) {
  try {
    const vectorStr = `[${embedding.join(',')}]`;
    const result = await pool.query(`
      SELECT DISTINCT ON (title)
             id, title, content, chunk_type, question_text,
             1 - (question_embedding <=> $1::vector) as similarity
      FROM chunks
      WHERE question_embedding IS NOT NULL
      ORDER BY title, question_embedding <=> $1::vector
    `, [vectorStr]);

    // Re-sort by similarity after DISTINCT and take top N
    const sorted = result.rows.sort((a, b) => b.similarity - a.similarity);
    return sorted.slice(0, limit);
  } catch (error) {
    console.error('Question match search error:', error);
    return [];
  }
}

// Fallback search: match against content embeddings
// Used when question matching doesn't find good results
async function searchByContentMatch(embedding, limit = 5) {
  try {
    const vectorStr = `[${embedding.join(',')}]`;
    const result = await pool.query(`
      SELECT DISTINCT ON (title)
             id, title, content, chunk_type,
             1 - (embedding <=> $1::vector) as similarity
      FROM chunks
      WHERE embedding IS NOT NULL
      ORDER BY title, embedding <=> $1::vector
    `, [vectorStr]);

    // Re-sort by similarity after DISTINCT and take top N
    const sorted = result.rows.sort((a, b) => b.similarity - a.similarity);
    return sorted.slice(0, limit);
  } catch (error) {
    console.error('Content match search error:', error);
    return [];
  }
}

// Main retrieval function - v3 with question-to-question matching
const QUESTION_MATCH_THRESHOLD = 0.75;  // High bar for question matching
const CONTENT_MATCH_THRESHOLD = 0.40;   // Lower bar for content fallback
const TOP_K = 1;  // Single match only — prevents cross-section bleed and hallucination

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

async function retrieveContent(query) {
  // Step 1: Expand aliases
  const expandedQuery = await expandAliases(query);
  console.log('[RAG] Query:', query);
  if (expandedQuery !== query) {
    console.log('[RAG] Expanded to:', expandedQuery);
  }

  // Step 2: Get embedding
  const embedding = await getEmbedding(expandedQuery);
  if (!embedding) {
    console.log('[RAG] Failed to get embedding');
    return { chunks: [], method: 'none' };
  }

  // Step 3: Primary search - match against question embeddings
  const questionMatches = await searchByQuestionMatch(embedding, TOP_K);
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
    return { chunks: goodQuestionMatches, method: 'question' };
  }

  // Step 5: Fallback to content matching
  console.log('[RAG] No good question match, falling back to content search');
  const contentMatches = await searchByContentMatch(embedding, TOP_K);
  const filteredContent = contentMatches.filter(r => r.similarity >= CONTENT_MATCH_THRESHOLD);

  console.log('[RAG] Content matches:', filteredContent.length);
  if (filteredContent.length > 0) {
    console.log('[RAG] Top content match:', filteredContent[0].title,
                'similarity:', filteredContent[0].similarity?.toFixed(3));
  }

  return { chunks: filteredContent, method: 'content' };
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

  try {
    const { messages, sessionId } = await request.json();

    // Validate messages
    if (!messages || !Array.isArray(messages) || messages.length === 0) {
      return new Response(JSON.stringify({ error: 'Messages array required' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    // Generate session ID if not provided
    const chatSessionId = sessionId || `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

    // Cap conversation history to prevent token overflow
    const MAX_MESSAGES = 20;
    const trimmedMessages = messages.slice(-MAX_MESSAGES);

    // Get the latest user message for RAG search
    const lastUserMessage = trimmedMessages.filter(m => m.role === 'user').pop();
    let ragContext = '';
    let retrievalInfo = { method: 'none', matches: [] };

    if (lastUserMessage) {
      const { chunks, method } = await retrieveContent(lastUserMessage.content);
      ragContext = formatRetrievedContent(chunks);
      // Capture retrieval info for logging
      retrievalInfo = {
        method,
        matches: chunks.map(c => ({
          section: c.title,
          score: c.similarity?.toFixed(3),
        })),
      };
    }

    // Combine system prompt with RAG context
    const enhancedSystemPrompt = SYSTEM_PROMPT + ragContext;

    // Create streaming response
    const stream = await anthropic.messages.stream({
      model: 'claude-sonnet-4-20250514',
      max_tokens: 1024,
      system: enhancedSystemPrompt,
      messages: trimmedMessages,
    });

    // Collect full response for logging
    let fullResponse = '';

    // Set up streaming response
    const encoder = new TextEncoder();
    const readableStream = new ReadableStream({
      async start(controller) {
        try {
          for await (const event of stream) {
            if (event.type === 'content_block_delta' && event.delta.type === 'text_delta') {
              fullResponse += event.delta.text;
              const data = JSON.stringify({ type: 'delta', text: event.delta.text });
              controller.enqueue(encoder.encode(`data: ${data}\n\n`));
            }
          }
          // Log the complete exchange after streaming finishes
          if (lastUserMessage) {
            logChatExchange(chatSessionId, lastUserMessage.content, fullResponse, retrievalInfo);
          }
          controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: 'done', sessionId: chatSessionId })}\n\n`));
          controller.close();
        } catch (error) {
          console.error('Streaming error:', error);
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
