import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

export async function POST(request: Request) {
  const botApiUrl = process.env.BOT_API_URL;
  
  if (!botApiUrl) {
    return NextResponse.json({ error: 'Backend BOT_API_URL not configured' }, { status: 500 });
  }

  try {
    const payload = await request.json();
    
    // Normalisasi URL
    let fetchUrl = botApiUrl.trim();
    if (!/^https?:\/\//i.test(fetchUrl)) {
      fetchUrl = `https://${fetchUrl}`;
    }
    fetchUrl = fetchUrl.replace(/\/+$/, '');
    
    const deleteUrl = `${fetchUrl}/api/delete-userbot`;
    
    console.log(`Forwarding delete-userbot request to Bot API: ${deleteUrl}`);
    
    const response = await fetch(deleteUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-telegram-init-data': request.headers.get('x-telegram-init-data') || '',
      },
      body: JSON.stringify(payload),
      next: { revalidate: 0 }
    });
    
    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error: any) {
    console.error(`Error forwarding delete-userbot request: ${error.message || error}`);
    return NextResponse.json({ error: error.message || 'Server Error' }, { status: 500 });
  }
}
