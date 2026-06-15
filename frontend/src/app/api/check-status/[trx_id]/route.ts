import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

export async function GET(
  request: Request,
  { params }: { params: { trx_id: string } }
) {
  const botApiUrl = process.env.BOT_API_URL;
  const { trx_id } = params;
  
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
    
    // Pastikan berakhiran /api/check-status/{trx_id}
    const checkStatusUrl = `${fetchUrl}/api/check-status/${trx_id}`;
    
    console.log(`Forwarding check status request to Bot API: ${checkStatusUrl}`);
    
    const response = await fetch(checkStatusUrl, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
      next: { revalidate: 0 }
    });
    
    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error: any) {
    console.error(`Error forwarding check status request: ${error.message || error}`);
    return NextResponse.json({ error: error.message || 'Server Error' }, { status: 500 });
  }
}
