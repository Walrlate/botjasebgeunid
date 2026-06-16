import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

export async function GET(
  request: Request,
  { params }: { params: { userId: string } }
) {
  const botApiUrl = process.env.BOT_API_URL;
  const { userId } = params;
  
  if (!botApiUrl) {
    return NextResponse.json({ error: 'Backend BOT_API_URL not configured' }, { status: 500 });
  }

  try {
    // Normalisasi URL
    let fetchUrl = botApiUrl.trim();
    if (!/^https?:\/\//i.test(fetchUrl)) {
      fetchUrl = `https://${fetchUrl}`;
    }
    fetchUrl = fetchUrl.replace(/\/+$/, '');
    
    // Pastikan berakhiran /api/user-stats/{userId}
    const userStatsUrl = `${fetchUrl}/api/user-stats/${userId}`;
    
    console.log(`Forwarding user-stats request to Bot API: ${userStatsUrl}`);
    
    const response = await fetch(userStatsUrl, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'x-telegram-init-data': request.headers.get('x-telegram-init-data') || '',
      },
      next: { revalidate: 0 }
    });
    
    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error: any) {
    console.error(`Error forwarding user-stats request: ${error.message || error}`);
    return NextResponse.json({ error: error.message || 'Server Error' }, { status: 500 });
  }
}
