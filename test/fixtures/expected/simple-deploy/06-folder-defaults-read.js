  // Forms/client_LocationBasedDefaults.html, one <a href> entry per folder.
  const folderDefaultValues = (text, path) => {
    const unescape = (s) => String(s).replace(/&quot;/g, '"').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');
    for (const entry of String(text).matchAll(/<a\s+href="([^"]*)"\s*>([\s\S]*?)<\/a>/g)) {
      let found = unescape(entry[1]);
      try { found = decodeURIComponent(found); } catch { /* compare the stored text */ }
      if (found !== path) continue;
      const values = new Map();
      for (const v of entry[2].matchAll(/<DefaultValue\s+FieldName="([^"]*)"\s*>([\s\S]*?)<\/DefaultValue>/g)) {
        values.set(unescape(v[1]), unescape(v[2]));
      }
      return values;
    }
    return new Map();
  };
