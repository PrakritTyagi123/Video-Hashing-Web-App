/* progress.js*/

function progressInit(jobId){
  const $ = id => document.getElementById(id);

  /*helpers*/
  const fmtMB    = b => ((b||0)/1048576).toFixed(1)+' MB';
  const fmtBytes = b => (b||0) > 1e9
                       ? ((b||0)/1073741824).toFixed(1)+' GB'
                       : fmtMB(b||0);
  const fmtETA   = s => new Date((s||0)*1000).toISOString().substr(11,8);
  const setBar   = (id,val)=>{
    const el=$(id), pct=Math.min(Math.max(val,0),100);
    el.style.width=pct+'%';
    el.innerText=Math.round(pct)+'%';
  };

  /*sortable ‘Remaining’ array*/
  let remainingData=[];
  window.sortRemain = by=>{
    remainingData.sort((a,b)=>
      by==='name' ? a.name.localeCompare(b.name)
                  : b.size-a.size);
    const box=$('remaining'); box.innerHTML='';
    remainingData.forEach(r=>{
      const li=document.createElement('li');
      li.className='list-group-item bg-secondary text-light py-1 text-truncate';
      li.textContent=r.name; box.appendChild(li);
    });
  };

  const pauseBtn=$('pauseBtn'), stopBtn=$('stopBtn');

  pauseBtn.onclick = ()=> pauseBtn.dataset.state!=='paused'
      ? fetch(`/control/${jobId}/pause`, {method:'POST'})
      : fetch(`/control/${jobId}/resume`,{method:'POST'});

  stopBtn.onclick  = ()=>{ stopBtn.disabled=true;
      fetch(`/control/${jobId}/stop`,{method:'POST'}); };

  document.addEventListener('keydown',e=>{
    if(e.code==='Space'){pauseBtn.click();e.preventDefault();}
    if(e.key==='s'||e.key==='S'){stopBtn.click();}
  });

  /*SSE stream*/
  const es = new EventSource(`/progress_stream/${jobId}`);
  es.onmessage = e =>{
    const d = JSON.parse(e.data);

    $('phase').textContent = d.stage||'';
    $('c1').textContent    = `${d.progress}/${d.total}`;
    $('bytes').textContent = `${fmtBytes(d.bytes_scanned)} / ${fmtBytes(d.bytes_total)}`;
    $('speed').textContent = d.speed + ' MB/s';
    $('eta').textContent   = fmtETA(d.eta);
    $('eta').title         = new Date(Date.now()+((d.eta||0)*1000))
                             .toLocaleTimeString();
    $('dbytes').textContent= fmtBytes(d.duplicate_bytes);
    $('groups').textContent= d.dup_groups;
    $('lg').textContent    = d.largest_group;
    $('sys').textContent   = `${d.cpu}% / ${d.mem}% / ${d.free} GB`;

    if(d.total) setBar('pbar', d.progress*100/d.total);
    setBar('fbar', d.file_pct);

    $('fn').textContent = d.current_file || '';

    if(d.thumbnail){
      const img=$('thumb');
      if(img.src!=="/thumb/"+d.thumbnail){
        img.src="/thumb/"+d.thumbnail;
        img.classList.remove('hidden');
      }
    }

    /*incremental lists*/
    if(d.scanned_names){
      const ul=$('scanned');
      d.scanned_names.slice(ul.children.length)
        .forEach(n=>{
          const li=document.createElement('li');
          li.className='list-group-item bg-secondary text-light py-1 text-truncate';
          li.textContent=n; ul.appendChild(li);
        });
    }
    if(d.remaining){
      remainingData = d.remaining;
      sortRemain('name');                   
    }

    /*duplicate panel (kept minimal for progress view)*/
    if(d.duplicates){
      const dupesUL=$('dupes');
      Object.entries(d.duplicates).forEach(([dig,arr])=>{
        if(!dupesUL.querySelector(`[data-d="${dig}"]`)){
          const li=document.createElement('li');
          li.dataset.d=dig;
          li.className='list-group-item bg-dark text-light py-1 small';
          li.textContent = dig.slice(0,12)+'… ('+arr.length+')';
          dupesUL.appendChild(li);
        }
      });
    }

    /*pause button look*/
    if('paused' in d){
      const paused=d.paused;
      pauseBtn.dataset.state = paused?'paused':'running';
      pauseBtn.className = paused
        ? 'btn btn-success btn-sm'
        : 'btn btn-warning btn-sm';
      pauseBtn.innerHTML = paused
        ? '<i class="fa fa-play"></i> <span>Resume</span>'
        : '<i class="fa fa-pause"></i> <span>Pause</span>';
    }

    /* finish state */
    if(d.done||d.stop){
      es.close();
      $('toResults').classList.remove('d-none');

      pauseBtn.disabled = stopBtn.disabled = true;
      pauseBtn.className = stopBtn.className = 'btn btn-secondary btn-sm';

      $('pbar').classList.replace('bg-success','bg-primary');
    }
  };
  es.onerror = ()=>{ console.warn('SSE closed'); es.close(); };
}
