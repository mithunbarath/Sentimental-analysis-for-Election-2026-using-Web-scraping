import { useState, useEffect, useMemo } from 'react';
import { db } from './firebase';
import { collection, query, orderBy, limit, onSnapshot } from 'firebase/firestore';
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, CartesianGrid } from 'recharts';
import './App.css';

function App() {
  const [records, setRecords] = useState([]);
  const [stats, setStats] = useState({ 
    total: 0, 
    dmk: 0, admk: 0, tvk: 0, bjp: 0,
    facebook: 0, instagram: 0, twitter: 0, youtube: 0,
    sentimentObj: { positive: 0, neutral: 0, negative: 0 },
    partySentiment: {
      dmk: { positive: 0, neutral: 0, negative: 0 },
      admk: { positive: 0, neutral: 0, negative: 0 },
      tvk: { positive: 0, neutral: 0, negative: 0 }
    }
  });
  const [selectedParty, setSelectedParty] = useState(null);
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
        sentimentObj: { positive: 0, neutral: 0, negative: 0 },
        partySentiment: {
          dmk: { positive: 0, neutral: 0, negative: 0 },
          admk: { positive: 0, neutral: 0, negative: 0 },
          tvk: { positive: 0, neutral: 0, negative: 0 }
        }
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
            
            // Party Specific Sentiment Aggregation
            if (newStats.partySentiment[p] !== undefined && data.nlp_sentiment) {
                let sent = data.nlp_sentiment.toLowerCase();
                if (sent.includes("1 star") || sent.includes("2 star") || sent === "negative") newStats.partySentiment[p].negative += 1;
                else if (sent.includes("5 star") || sent.includes("4 star") || sent === "positive") newStats.partySentiment[p].positive += 1;
                else newStats.partySentiment[p].neutral += 1;
            }
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
  
  // Prepare data for recharts
  const platformData = [
    { name: 'Facebook', value: stats.facebook, color: '#3b82f6' },
    { name: 'Instagram', value: stats.instagram, color: '#ec4899' },
    { name: 'Twitter', value: stats.twitter, color: '#cbd5e1' },
    { name: 'YouTube', value: stats.youtube, color: '#ef4444' }
  ].filter(d => d.value > 0);

  const partyData = [
    { name: 'DMK', id: 'dmk', value: stats.dmk, color: '#ef4444' },
    { name: 'ADMK', id: 'admk', value: stats.admk, color: '#eab308' },
    { name: 'TVK', id: 'tvk', value: stats.tvk, color: '#f97316' },
    { name: 'BJP', id: 'bjp', value: stats.bjp, color: '#f87171' }
  ].filter(d => d.value > 0);

  const sentimentData = [
    { 
      name: 'DMK', 
      Positive: stats.partySentiment.dmk.positive, 
      Neutral: stats.partySentiment.dmk.neutral, 
      Negative: stats.partySentiment.dmk.negative,
      id: 'dmk'
    },
    { 
      name: 'ADMK', 
      Positive: stats.partySentiment.admk.positive, 
      Neutral: stats.partySentiment.admk.neutral, 
      Negative: stats.partySentiment.admk.negative,
      id: 'admk'
    },
    { 
      name: 'TVK', 
      Positive: stats.partySentiment.tvk.positive, 
      Neutral: stats.partySentiment.tvk.neutral, 
      Negative: stats.partySentiment.tvk.negative,
      id: 'tvk'
    }
  ];

  const [searchKeyword, setSearchKeyword] = useState('');

  const handlePartyClick = (data) => {
    // Determine the clicked party ID depending on which chart was clicked
    let clickedId = null;
    if (data && data.payload && data.payload.id) {
       clickedId = data.payload.id; // Pie chart click
    } else if (data && data.activePayload && data.activePayload.length) {
       clickedId = data.activePayload[0].payload.id; // Bar chart click
    }
    
    if (clickedId) {
       setSelectedParty(prev => prev === clickedId ? null : clickedId);
    }
  };

  const filteredRecords = useMemo(() => {
    let result = records;
    if (selectedParty) {
      result = result.filter(post => 
        post.parties_mentioned && 
        post.parties_mentioned.map(p => p.toLowerCase()).includes(selectedParty)
      );
    }
    if (searchKeyword.trim() !== '') {
      const keywordLower = searchKeyword.toLowerCase();
      result = result.filter(post => 
        (post.text && post.text.toLowerCase().includes(keywordLower)) ||
        (post.author && post.author.toLowerCase().includes(keywordLower))
      );
    }
    return result;
  }, [records, selectedParty, searchKeyword]);

  const downloadCSV = () => {
    if (filteredRecords.length === 0) return;
    
    const headers = ['Platform', 'Author', 'Timestamp', 'Sentiment', 'Parties Mentioned', 'Kongu Related', 'URL', 'Text'];
    
    const csvRows = filteredRecords.map(post => {
      // Escape quotes for CSV format
      const escapeCsv = (str) => `"${(str || '').toString().replace(/"/g, '""')}"`;
      
      return [
        post.platform || '',
        escapeCsv(post.author),
        post.timestamp || '',
        post.nlp_sentiment || '',
        escapeCsv((post.parties_mentioned || []).join(', ')),
        post.is_kongu_related ? 'Yes' : 'No',
        post.url || '',
        escapeCsv(post.text)
      ].join(',');
    });
    
    const csvString = [headers.join(','), ...csvRows].join('\n');
    const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    
    link.setAttribute('href', url);
    link.setAttribute('download', `intel_export_${searchKeyword ? searchKeyword.replace(/\s+/g, '_') + '_' : ''}${new Date().getTime()}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

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
            
            <div className="stat-card glass">
              <h3>Sentiment Overview (All)</h3>
              <div className="sub-stats">
                <div>
                  <span style={{color: '#10b981'}}>Positive</span>
                  <strong>{stats.sentimentObj.positive}</strong>
                </div>
                <div>
                  <span style={{color: '#94a3b8'}}>Neutral</span>
                  <strong>{stats.sentimentObj.neutral}</strong>
                </div>
                <div>
                  <span style={{color: '#ef4444'}}>Negative</span>
                  <strong>{stats.sentimentObj.negative}</strong>
                </div>
              </div>
            </div>
            
            <div className="stat-card glass">
              <h3>Coverage Top Party</h3>
              <div className="stat-value" style={{fontSize: '2.5rem', marginTop: '0.6rem'}}>
                {stats.dmk >= stats.admk && stats.dmk >= stats.tvk ? "DMK" : 
                 stats.admk >= stats.dmk && stats.admk >= stats.tvk ? "ADMK" : 
                 stats.tvk > stats.dmk && stats.tvk > stats.admk ? "TVK" : "None"}
              </div>
              <div className="stat-label" style={{marginTop: '0.6rem'}}>Highest Mention Count</div>
            </div>
          </section>

          <div className="dashboard-content">
            <main className="feed-container main-feed">
              <div className="feed-header-wrapper">
                <div className="feed-header">
                  <h2>{selectedParty ? `${selectedParty.toUpperCase()} Live Feed` : "Real-Time Live Feed"}</h2>
                  
                  <div className="feed-controls">
                    <div className="search-box glass">
                      <span className="search-icon">🔍</span>
                      <input 
                        type="text" 
                        placeholder="Filter by keyword or district..." 
                        value={searchKeyword}
                        onChange={(e) => setSearchKeyword(e.target.value)}
                        className="keyword-input"
                      />
                      {searchKeyword && (
                        <button className="clear-text-btn" onClick={() => setSearchKeyword('')}>×</button>
                      )}
                    </div>
                    
                    <button className="download-csv-btn glass" onClick={downloadCSV} disabled={filteredRecords.length === 0}>
                      ⬇️ Export CSV
                    </button>
                  </div>
                </div>

                <div className="feed-header-actions" style={{ marginBottom: "1.5rem" }}>
                  {selectedParty && (
                    <button className="clear-filter-btn" onClick={() => setSelectedParty(null)}>
                      × Clear Party Filter ({selectedParty.toUpperCase()})
                    </button>
                  )}
                  <span className="record-count">{filteredRecords.length} Updates</span>
                </div>
              </div>

              <div className="feed-grid">
                {filteredRecords.map((post) => (
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
                        <a href={post.url} target="_blank" rel="noreferrer" className="view-btn" onClick={(e) => { e.stopPropagation(); }}>
                          View Source ↗
                        </a>
                      )}
                    </footer>
                  </article>
                ))}
                
                {filteredRecords.length === 0 && (
                  <div className="empty-state glass">
                    <div className="empty-icon">📂</div>
                    <h3>No Intelligence Recorded {selectedParty && "for " + selectedParty.toUpperCase()} Yet</h3>
                    {!selectedParty && <p>Start your Python scraper using "python main.py". Firestore will push the data here instantly.</p>}
                  </div>
                )}
              </div>
            </main>

            <aside className="side-infographics">
              <div className="stat-card glass interactive-chart">
                <h3>Party Share of Voice</h3>
                <p className="chart-instruction">Click a slice to filter feed by party!</p>
                <div className="pie-container" style={{ margin: "1rem 0" }}>
                  <ResponsiveContainer width="100%" height={250}>
                    <PieChart>
                      <Pie
                        data={partyData}
                        cx="50%"
                        cy="50%"
                        innerRadius={60}
                        outerRadius={90}
                        paddingAngle={5}
                        dataKey="value"
                        onClick={handlePartyClick}
                        cursor="pointer"
                      >
                        {partyData.map((entry, index) => (
                          <Cell 
                            key={`cell-${index}`} 
                            fill={entry.color} 
                            opacity={selectedParty === entry.id ? 1 : (selectedParty ? 0.3 : 1)}
                            stroke={selectedParty === entry.id ? "#fff" : "none"}
                            strokeWidth={2}
                          />
                        ))}
                      </Pie>
                      <Tooltip contentStyle={{backgroundColor: '#07090F', borderColor: '#333', borderRadius: '8px'}} itemStyle={{color: '#F8FAFC'}} />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div className="stat-card glass interactive-chart">
                <h3>Sentiment by Party</h3>
                <p className="chart-instruction">Click a corresponding bar to isolate feed!</p>
                <div className="bar-container" style={{ margin: "1rem 0" }}>
                  <ResponsiveContainer width="100%" height={280}>
                    <BarChart
                      data={sentimentData}
                      margin={{ top: 20, right: 30, left: -20, bottom: 5 }}
                      onClick={handlePartyClick}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#333" vertical={false} />
                      <XAxis dataKey="name" stroke="#94A3B8" />
                      <YAxis stroke="#94A3B8" />
                      <Tooltip 
                        contentStyle={{backgroundColor: '#07090F', borderColor: '#333', borderRadius: '8px', color: '#F8FAFC'}}
                        itemStyle={{color: '#F8FAFC'}}
                        labelStyle={{color: '#94A3B8'}}
                        cursor={{fill: 'rgba(255,255,255,0.05)'}}
                      />
                      <Legend />
                      <Bar dataKey="Positive" stackId="a" fill="#10b981" cursor="pointer" />
                      <Bar dataKey="Neutral" stackId="a" fill="#94a3b8" cursor="pointer" />
                      <Bar dataKey="Negative" stackId="a" fill="#ef4444" cursor="pointer" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div className="stat-card glass">
                <h3>Platform Intelligence</h3>
                <div className="pie-container" style={{ margin: "1rem 0" }}>
                  <ResponsiveContainer width="100%" height={250}>
                    <PieChart>
                      <Pie
                        data={platformData}
                        cx="50%"
                        cy="50%"
                        innerRadius={50}
                        outerRadius={90}
                        paddingAngle={3}
                        dataKey="value"
                      >
                        {platformData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip contentStyle={{backgroundColor: '#07090F', borderColor: '#333', borderRadius: '8px'}} itemStyle={{color: '#F8FAFC'}} />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </div>

            </aside>
          </div>
        </>
      )}
    </div>
  );
}

export default App;

