import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

export async function GET() {
  const botApiUrl = process.env.BOT_API_URL;

  if (!botApiUrl) {
    return NextResponse.json({ status: false, error: 'BOT_API_URL not configured' }, { status: 500 });
  }

  try {
    let fetchUrl = botApiUrl.trim();
    if (!/^https?:\/\//i.test(fetchUrl)) {
      fetchUrl = `https://${fetchUrl}`;
    }
    fetchUrl = fetchUrl.replace(/\/+$/, '');
    const url = `${fetchUrl}/api/admin-slots`;

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000);

    const response = await fetch(url, {
      signal: controller.signal,
      next: { revalidate: 0 },
    });

    clearTimeout(timeoutId);

    if (response.ok) {
      const data = await response.json();
      return NextResponse.json(data);
    } else {
      const errText = await response.text();
      console.error(`admin-slots API error ${response.status}: ${errText}`);
      return NextResponse.json({ status: false, error: `Bot API error: ${response.status}` }, { status: response.status });
    }
  } catch (error: any) {
    console.error(`Error fetching admin-slots: ${error.message || error}`);
    return NextResponse.json({ status: false, error: error.message || 'Server Error' }, { status: 500 });
  }
}
