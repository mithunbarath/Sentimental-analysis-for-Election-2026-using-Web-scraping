import { useState, useEffect } from 'react';
import { db } from './firebase';
import { collection, query, orderBy, limit, onSnapshot } from 'firebase/firestore';
import './App.css';

function App() {
  const [records, setRecords] = useState([]);
  const [stats, setStats] = useState({ 
    total: 0, 
    dmk: 0, admk: 0, tvk: 0, bjp: 0,
    facebook: 0, instagram: 0, twitter: 0, youtube: 0,
    sentimentObj: { positive: 0, neutral: 0, negative: 0 }
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Listen to the 'social_records' collection, ordered by timestamp descending, limit to 1000 posts for deeper intelligence
    const q = query(
      collection(db, "social_records"), 
      orderBy("timestamp", "desc"), 
      limit(1000)
    );

    const unsubscribe = onSnapshot(q, (snapshot) => {
      const newRecords = [];
      const newStats = { 
        total: 0, 
        dmk: 0, admk: 0, tvk: 0, bjp: 0,
        facebook: 0, instagram: 0, twitter: 0, youtube: 0,
        sentimentObj: { positive: 0, neutral: 0, negative: 0 }
      };
      
      snapshot.forEach((doc) => {
        const data = doc.data();
        newRecords.push({ id: doc.id, ...data });
        
        // Compute statistics for the dashboard natively from the snapshot
        newStats.total += 1;
        
        // Count Platforms
        if (data.platform) {
          const plat = data.platform.toLowerCase();
          if (newStats[plat] !== undefined) newStats[plat] += 1;
        }

        // Count Parties
        if (data.parties_mentioned && Array.isArray(data.parties_mentioned)) {
          data.parties_mentioned.forEach(party => {
            const p = party.toLowerCase();
            if (newStats[p] !== undefined) newStats[p] += 1;
          });
        }
        
        // Sentiment Aggregation
        if (data.nlp_sentiment) {
            let sent = data.nlp_sentiment.toLowerCase();
            if (sent.includes("1 star") || sent.includes("2 star") || sent === "negative") newStats.sentimentObj.negative += 1;
            else if (sent.includes("5 star") || sent.includes("4 star") || sent === "positive") newStats.sentimentObj.positive += 1;
            else newStats.sentimentObj.neutral += 1;
        }
      });
      
      setRecords(newRecords);
      setStats(newStats);
      setLoading(false);
    }, (error) => {
      console.error("Error fetching Firestore real-time data:", error);
      setLoading(false);
    });

    return () => unsubscribe();
  }, []);

  const formatDate = (dateString) => {
    if (!dateString) return "Just now";
    const date = new Date(dateString);
    if (isNaN(date)) return dateString;
    return date.toLocaleString('en-US', { 
      month: 'short', day: 'numeric', 
      hour: '2-digit', minute: '2-digit' 
    });
  };

  const getPlatformIcon = (platform) => {
    switch(platform?.toLowerCase()) {
      case 'facebook': return <div className="platform-icon fb">f</div>;
      case 'instagram': return <div className="platform-icon ig">i</div>;
      case 'twitter': return <div className="platform-icon tw">X</div>;
      case 'youtube': return <div className="platform-icon yt">►</div>;
      default: return <div className="platform-icon">🌐</div>;
    }
  };
  
  // Calculate Progress bar widths
  const pfTotal = Math.max(1, stats.facebook + stats.instagram + stats.twitter + stats.youtube);
  const pTotal = Math.max(1, stats.dmk + stats.admk + stats.tvk + stats.bjp);
  const sTotal = Math.max(1, stats.sentimentObj.positive + stats.sentimentObj.neutral + stats.sentimentObj.negative);

  return (
    <div className="dashboard-container">
      <header className="dashboard-header">
        <div className="header-glow"></div>
        <h1>Kongu Region Political Intel <span className="live-badge">Live</span></h1>
        <p>Real-time social media intelligence streaming directly from Python scrapers via Firebase Firestore.</p>
      </header>

      {loading ? (
        <div className="loader-container">
          <div className="pulse-loader"></div>
          <p>Syncing secure Firestore connection...</p>
        </div>
      ) : (
        <>
          <section className="stats-grid">
            <div className="stat-card glass variant-primary">
              <h3>Ingested Posts</h3>
              <div className="stat-value">{stats.total}</div>
              <div className="stat-label">Last 1000 limit applied</div>
              <div className="sparkline"></div>
            </div>
            
            <div className="stat-card glass chart-card">
              <h3>Platform Intelligence</h3>
              <div className="chart-bar-container">
                <div className="chart-bar" style={{ width: `${(stats.facebook / pfTotal) * 100}%`, background: '#3b82f6' }}></div>
                <div className="chart-bar" style={{ width: `${(stats.instagram / pfTotal) * 100}%`, background: '#ec4899' }}></div>
                <div className="chart-bar" style={{ width: `${(stats.twitter / pfTotal) * 100}%`, background: '#cbd5e1' }}></div>
                <div className="chart-bar" style={{ width: `${(stats.youtube / pfTotal) * 100}%`, background: '#ef4444' }}></div>
              </div>
              <div className="chart-legend">
                <div><span style={{background: '#3b82f6'}}></span>FB <strong>{stats.facebook}</strong></div>
                <div><span style={{background: '#ec4899'}}></span>IG <strong>{stats.instagram}</strong></div>
                <div><span style={{background: '#cbd5e1'}}></span>X <strong>{stats.twitter}</strong></div>
                <div><span style={{background: '#ef4444'}}></span>YT <strong>{stats.youtube}</strong></div>
              </div>
            </div>

            <div className="stat-card glass chart-card">
              <h3>Party Frequency</h3>
              <div className="chart-bar-container">
                <div className="chart-bar" style={{ width: `${(stats.dmk / pTotal) * 100}%`, background: '#ef4444' }}></div>
                <div className="chart-bar" style={{ width: `${(stats.admk / pTotal) * 100}%`, background: '#eab308' }}></div>
                <div className="chart-bar" style={{ width: `${(stats.tvk / pTotal) * 100}%`, background: '#f97316' }}></div>
              </div>
              <div className="chart-legend">
                <div className="party-dmk"><span style={{background: '#ef4444'}}></span>DMK <strong>{stats.dmk}</strong></div>
                <div className="party-admk"><span style={{background: '#eab308'}}></span>ADMK <strong>{stats.admk}</strong></div>
                <div className="party-tvk"><span style={{background: '#f97316'}}></span>TVK <strong>{stats.tvk}</strong></div>
              </div>
            </div>
            
            <div className="stat-card glass chart-card">
              <h3>Political Sentiment</h3>
              <div className="chart-bar-container">
                <div className="chart-bar" style={{ width: `${(stats.sentimentObj.positive / sTotal) * 100}%`, background: '#10b981' }}></div>
                <div className="chart-bar" style={{ width: `${(stats.sentimentObj.neutral / sTotal) * 100}%`, background: '#94a3b8' }}></div>
                <div className="chart-bar" style={{ width: `${(stats.sentimentObj.negative / sTotal) * 100}%`, background: '#ef4444' }}></div>
              </div>
              <div className="chart-legend">
                <div><span style={{background: '#10b981'}}></span>Positive <strong>{stats.sentimentObj.positive}</strong></div>
                <div><span style={{background: '#94a3b8'}}></span>Neutral <strong>{stats.sentimentObj.neutral}</strong></div>
                <div><span style={{background: '#ef4444'}}></span>Negative <strong>{stats.sentimentObj.negative}</strong></div>
              </div>
            </div>
          </section>

          <main className="feed-container">
            <div className="feed-header">
              <h2>Real-Time Live Feed</h2>
              <span className="record-count">{records.length} Pulled updates</span>
            </div>

            <div className="feed-grid">
              {records.map((post) => (
                <article key={post.id} className="feed-card glass">
                  <header className="card-header">
                    {getPlatformIcon(post.platform)}
                    <div className="meta-info">
                      <span className="author">{post.author || post.platform}</span>
                      <span className="time">{formatDate(post.timestamp)}</span>
                    </div>
                  </header>
                  
                  <p className="post-text">{post.text}</p>
                  
                  <footer className="card-footer">
                    <div className="tags">
                      {post.parties_mentioned && post.parties_mentioned.map(party => (
                        <span key={party} className={`tag tag-${party.toLowerCase()}`}>{party}</span>
                      ))}
                      {post.is_kongu_related && (
                        <span className="tag tag-region">Kongu Zone</span>
                      )}
                      {post.nlp_sentiment && (
                          <span className={`tag tag-sentiment ${post.nlp_sentiment.toLowerCase().includes('positive') || post.nlp_sentiment.includes('5 star') ? 'positive' : post.nlp_sentiment.toLowerCase().includes('negative') || post.nlp_sentiment.includes('1 star') ? 'negative' : 'neutral'}`}>
                              {post.nlp_sentiment}
                          </span>
                      )}
                    </div>
                    {post.url && (
                      <a href={post.url} target="_blank" rel="noreferrer" className="view-btn">
                        View Source ↗
                      </a>
                    )}
                  </footer>
                </article>
              ))}
              
              {records.length === 0 && (
                <div className="empty-state glass">
                  <div className="empty-icon">📂</div>
                  <h3>No Intelligence Recorded Yet</h3>
                  <p>Start your Python scraper using "python main.py". Firestore will push the data here instantly.</p>
                </div>
              )}
            </div>
          </main>
        </>
      )}
    </div>
  );
}

export default App;

