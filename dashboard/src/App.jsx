import { useState, useEffect } from 'react';
import { db } from './firebase';
import { collection, query, orderBy, limit, onSnapshot } from 'firebase/firestore';
import './App.css';

function App() {
  const [records, setRecords] = useState([]);
  const [stats, setStats] = useState({ total: 0, dmk: 0, admk: 0, tvk: 0, facebook: 0, instagram: 0, twitter: 0, youtube: 0 });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Listen to the 'social_records' collection, ordered by timestamp descending, limit to 200 posts
    const q = query(
      collection(db, "social_records"), 
      orderBy("timestamp", "desc"), 
      limit(200)
    );

    const unsubscribe = onSnapshot(q, (snapshot) => {
      const newRecords = [];
      const newStats = { total: 0, dmk: 0, admk: 0, tvk: 0, facebook: 0, instagram: 0, twitter: 0, youtube: 0 };
      
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

  return (
    <div className="dashboard-container">
      <header className="dashboard-header">
        <div className="header-glow"></div>
        <h1>Palladam Political Intel <span className="live-badge">Live</span></h1>
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
              <div className="stat-label">Last 200 limit applied</div>
            </div>
            
            <div className="stat-card glass">
              <h3>Platform Intel</h3>
              <div className="sub-stats">
                <div><span>FB</span> <strong>{stats.facebook}</strong></div>
                <div><span>IG</span> <strong>{stats.instagram}</strong></div>
                <div><span>X/TW</span> <strong>{stats.twitter}</strong></div>
              </div>
            </div>

            <div className="stat-card glass">
              <h3>Party Frequency</h3>
              <div className="sub-stats">
                <div className="party-dmk"><span>DMK</span> <strong>{stats.dmk}</strong></div>
                <div className="party-admk"><span>ADMK</span> <strong>{stats.admk}</strong></div>
                <div className="party-tvk"><span>TVK</span> <strong>{stats.tvk}</strong></div>
              </div>
            </div>
          </section>

          <main className="feed-container">
            <div className="feed-header">
              <h2>Real-Time Feed</h2>
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
                      {post.is_palladam_related && (
                        <span className="tag tag-region">Palladam</span>
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
