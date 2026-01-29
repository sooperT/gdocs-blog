import pg from 'pg';

// Database connection
const pool = new pg.Pool({
  connectionString: process.env.NILEDB_URL,
  ssl: { rejectUnauthorized: false }
});

// Get embedding from Voyage AI
async function getEmbedding(text) {
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

  if (!response.ok) {
    const error = await response.text();
    console.error('Voyage API error:', error);
    return null;
  }

  const data = await response.json();
  return data.data[0].embedding;
}

export default async (request, context) => {
  const url = new URL(request.url);
  const query = url.searchParams.get('q');

  if (!query) {
    return new Response(JSON.stringify({ error: 'Query parameter q required' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  try {
    console.log('Searching for:', query);
    const embedding = await getEmbedding(query);
    console.log('Got embedding:', embedding ? embedding.length : 'null');

    if (!embedding) {
      return new Response(JSON.stringify({ error: 'Failed to get embedding' }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' }
      });
    }

    // Format as pgvector expects: [1,2,3,...]
    const vectorStr = `[${embedding.join(',')}]`;
    console.log('Vector string length:', vectorStr.length);

    const result = await pool.query(`
      SELECT title, source, content,
             1 - (embedding <=> $1::vector) as similarity
      FROM chunks
      ORDER BY embedding <=> $1::vector
      LIMIT 3
    `, [vectorStr]);
    console.log('Query returned:', result.rows.length, 'rows');

    return new Response(JSON.stringify({
      query,
      embeddingLength: embedding.length,
      results: result.rows
    }, null, 2), {
      headers: { 'Content-Type': 'application/json' }
    });

  } catch (error) {
    console.error('Search error:', error);
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
};

export const config = {
  path: '/api/search',
};
