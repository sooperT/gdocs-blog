// Product Manager Simulation 2008 — v0.1
(() => {
  const canvas = document.getElementById('game');
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  const GROUND_Y = H - 60;
  const GRID = 16;

  const ui = {
    price: document.getElementById('price'),
    priceVal: document.getElementById('priceVal'),
    release: document.getElementById('release'),
    releaseVal: document.getElementById('releaseVal'),
    speed: document.getElementById('speed'),
    speedVal: document.getElementById('speedVal'),
    pauseBtn: document.getElementById('pauseBtn'),
    resetBtn: document.getElementById('resetBtn'),
    mrr: document.getElementById('mrr'),
    cash: document.getElementById('cash'),
    active: document.getElementById('active'),
    churned: document.getElementById('churned'),
    referrals: document.getElementById('referrals'),
    nrr: document.getElementById('nrr'),
    toolbar: document.getElementById('toolbar'),
  };

  let tool = 'ramp';
  ui.toolbar.addEventListener('click', (e) => {
    if (e.target.tagName === 'BUTTON' && e.target.dataset.tool) {
      tool = e.target.dataset.tool;
    }
  });

  const world = {
    t: 0,
    paused: false,
    cats: [],
    tiles: [],
    price: +ui.price.value, // dollars per month for premium
    baseARPU: 15,
    arpu: +ui.price.value,
    releaseRate: +ui.release.value, // cats per second
    speedMult: +ui.speed.value,
    churned: 0,
    referrals: 0,
    mrr: 0,
    cash: 50000,
    monthMRRStart: 0,
    monthChurn: 0,
    monthExpansion: 0,
  };

  function fmtMoney(n) {
    return '$' + Math.round(n).toLocaleString();
  }

  function clamp(v, a, b){ return Math.max(a, Math.min(b, v)); }

  ui.price.addEventListener('input', () => {
    world.price = +ui.price.value;
    world.arpu = world.price;
    ui.priceVal.textContent = world.price.toFixed(0);
  });
  ui.release.addEventListener('input', () => {
    world.releaseRate = +ui.release.value;
    ui.releaseVal.textContent = world.release.value;
  });
  ui.speed.addEventListener('input', () => {
    world.speedMult = +ui.speed.value;
    ui.speedVal.textContent = world.speed.value;
  });
  ui.pauseBtn.addEventListener('click', () => { world.paused = !world.paused; ui.pauseBtn.textContent = world.paused ? 'Resume' : 'Pause'; });
  ui.resetBtn.addEventListener('click', reset);

  // Place initial terrain patches
  function placeTile(x, y, kind, level=1){
    world.tiles.push({x: Math.round(x/GRID)*GRID, y: Math.round(y/GRID)*GRID, kind, level});
  }

  // Seed a few helpful tiles
  placeTile(200, GROUND_Y-32, 'ramp', 1);
  placeTile(360, GROUND_Y-32, 'toy', 1);
  placeTile(520, GROUND_Y-32, 'pond', 1);
  placeTile(680, GROUND_Y-32, 'billboard', 1);
  placeTile(820, GROUND_Y-32, 'pit', 1);

  // User placement with cash cost
  const costs = { ramp: 200, toy: 300, pit: 0, pond: 400, billboard: 250 };
  canvas.addEventListener('click', (e) => {
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const gx = Math.round(x/GRID)*GRID;
    const gy = Math.round(y/GRID)*GRID;
    if (world.cash >= costs[tool]) {
      placeTile(gx, gy, tool, 1);
      world.cash -= costs[tool];
    }
  });

  // Spawn cats steadily
  let spawnAccumulator = 0;
  function spawn(dt){
    // acquisition elasticity: higher price reduces acquisition
    const priceFactor = Math.exp(-0.06 * ((world.price / world.baseARPU) - 1));
    const rate = world.releaseRate * priceFactor;
    spawnAccumulator += dt * rate;
    while (spawnAccumulator >= 1) {
      spawnAccumulator -= 1;
      const y = GROUND_Y - 8 + (Math.random()*6 - 3);
      world.cats.push({
        id: (Math.random()*1e9)|0,
        x: 8,
        y,
        v: 35 + Math.random()*10,
        happy: 0.5 + Math.random()*0.3,
        activated: false,
        tier: Math.random() < 0.2 ? 'pro' : 'free', // basic freemium mix
        alive: true,
        tOnMap: 0,
      });
    }
  }

  function frictionAt(x,y){
    // baseline slight friction
    let mu = 0.12;
    for (const t of world.tiles){
      if (Math.abs(t.x - x) < GRID*2 && Math.abs(t.y - y) < GRID*1.5){
        switch (t.kind){
          case 'ramp': mu -= 0.08 * t.level; break;
          case 'billboard': mu += 0.05 * t.level; break;
          case 'toy': mu -= 0.05 * t.level; break; // dwell
          case 'pond': mu -= 0.03 * t.level; break;
          case 'pit': mu += 0.25 * t.level; break;
        }
      }
    }
    return clamp(mu, 0.02, 0.6);
  }

  function applyTiles(cat, dt){
    for (const t of world.tiles){
      if (Math.abs(t.x - cat.x) < GRID && Math.abs(t.y - cat.y) < GRID){
        switch (t.kind){
          case 'toy':
            cat.happy = clamp(cat.happy + 0.15*dt, 0, 1.5);
            if (!cat.activated) cat.activated = true;
            break;
          case 'pond':
            cat.happy = clamp(cat.happy + 0.08*dt, 0, 1.5);
            // referral chance grows with happiness and activation
            if (cat.activated && Math.random() < 0.015*dt*cat.happy){
              world.referrals++;
              world.cats.push({
                id: (Math.random()*1e9)|0,
                x: 8, y: GROUND_Y-8 + (Math.random()*6 - 3),
                v: 35 + Math.random()*10,
                happy: 0.55 + Math.random()*0.3,
                activated: false,
                tier: Math.random() < 0.35 ? 'pro' : 'free',
                alive: true, tOnMap: 0,
              });
            }
            break;
          case 'billboard':
            // small unhappiness due to ads
            cat.happy = clamp(cat.happy - 0.05*dt, 0, 1.5);
            break;
          case 'pit':
            // chance to fall (churn)
            if (Math.random() < 0.6*dt){
              cat.alive = false;
              world.churned++;
            }
            break;
        }
      }
    }
  }

  function updateCat(cat, dt){
    cat.tOnMap += dt;
    // happiness decay over time
    cat.happy = clamp(cat.happy - 0.04*dt, 0, 1.5);
    // price-linked churn elasticity for premium
    const priceChurnKick = cat.tier === 'pro' ? 0.0 + Math.max(0, (world.price/world.baseARPU - 1))*0.02 : 0;
    // churn if too unhappy or off-screen
    if (cat.happy < 0.05 + priceChurnKick){
      cat.alive = false; world.churned++; return;
    }
    // movement
    const mu = frictionAt(cat.x, cat.y);
    const v = (cat.v * (1.0 - mu)) * world.speedMult;
    cat.x += v * dt;
    // exit to the right (survived a month-equivalent path)
    if (cat.x > W - 8){
      // loop back with slight happiness decay: long-term retention
      cat.x = 8;
      cat.happy = clamp(cat.happy - 0.1, 0, 1.5);
    }
  }

  // finance
  const ticksPerMonth = 300; // ~30s at 10 tps
  let tickCounter = 0;

  function financeTick(dt){
    // MRR accrual per cat; free tier pays 0
    for (const c of world.cats){
      if (!c.alive) continue;
      if (c.tier === 'pro'){
        // unhappy premiums pay less (downgrade pressure)
        const arpuEff = world.arpu * (0.6 + 0.4 * clamp(c.happy, 0, 1));
        world.mrr += arpuEff / ticksPerMonth;
      }
    }
    // Simple burn: base + infra per active + placement spending (already deducted)
    const baseBurnPM = 20000;
    const infraPerCatPM = 0.8; // per active per month
    const active = world.cats.filter(c => c.alive).length;
    const burnThisTick = (baseBurnPM + infraPerCatPM * active) / ticksPerMonth;
    const revThisTick = world.mrr / ticksPerMonth; // smoothed display contribution
    world.cash += revThisTick - burnThisTick;
  }

  function step(dt){
    if (world.paused) return;
    world.t += dt;
    spawn(dt);
    // update cats
    for (let i = world.cats.length - 1; i >= 0; i--){
      const c = world.cats[i];
      if (!c.alive){ world.cats.splice(i,1); continue; }
      applyTiles(c, dt);
      updateCat(c, dt);
    }
    financeTick(dt);
  }

  // Draw
  function draw(){
    // background
    ctx.fillStyle = '#0a1118';
    ctx.fillRect(0,0,W,H);

    // ground
    ctx.fillStyle = '#0d1825';
    ctx.fillRect(0,GROUND_Y, W, H-GROUND_Y);

    // tiles
    for (const t of world.tiles){
      switch (t.kind){
        case 'ramp': ctx.fillStyle = '#2a6da8'; break;
        case 'toy': ctx.fillStyle = '#2d8a4f'; break;
        case 'pond': ctx.fillStyle = '#2c5a9e'; break;
        case 'pit': ctx.fillStyle = '#8a2e2e'; break;
        case 'billboard': ctx.fillStyle = '#8a7b2e'; break;
      }
      ctx.fillRect(t.x-12, t.y-12, 24, 24);
      // simple pixel accent
      ctx.fillStyle = '#00000022';
      ctx.fillRect(t.x-12, t.y-12, 24, 6);
    }

    // cats
    for (const c of world.cats){
      if (!c.alive) continue;
      // body color varies with happiness
      const happy = clamp(c.happy, 0, 1);
      const base = 120 + Math.floor(80*happy);
      ctx.fillStyle = `rgb(${base},${base},${200})`;
      ctx.fillRect(c.x-4, c.y-6, 8, 8);
      // ears
      ctx.fillRect(c.x-5, c.y-8, 3, 3);
      ctx.fillRect(c.x+2, c.y-8, 3, 3);
      // eye
      ctx.fillStyle = '#0b0f14';
      ctx.fillRect(c.x, c.y-4, 2, 2);
      // premium collar
      if (c.tier === 'pro'){
        ctx.fillStyle = '#ffd166';
        ctx.fillRect(c.x-4, c.y-1, 8, 2);
      }
      // activation sparkle
      if (c.activated){
        ctx.fillStyle = '#9be7ff';
        ctx.fillRect(c.x+5, c.y-10, 2, 2);
      }
    }

    // HUD overlay lines
    ctx.strokeStyle = '#142033';
    ctx.beginPath();
    for (let x=0; x<W; x+=GRID) { ctx.moveTo(x, GROUND_Y); ctx.lineTo(x, GROUND_Y+6); }
    ctx.stroke();
  }

  // UI update
  function updateUI(){
    ui.mrr.textContent = fmtMoney(world.mrr);
    ui.cash.textContent = fmtMoney(world.cash);
    ui.active.textContent = world.cats.length.toString();
    ui.churned.textContent = world.churned.toString();
    ui.referrals.textContent = world.referrals.toString();
    // rough NRR proxy from price changes & churn in last pseudo-month
    const start = Math.max(1, world.monthMRRStart);
    const estNRR = clamp((start - world.monthChurn + world.monthExpansion)/start, 0.5, 1.5);
    ui.nrr.textContent = Math.round(estNRR*100) + '%';
  }

  // Month cycle book-keeping for NRR-ish display
  let monthAccumulator = 0;
  function monthCycle(dt){
    monthAccumulator += dt;
    if (monthAccumulator >= (ticksPerMonth/10)*0.1){ /* keep smooth */ }
    if (monthAccumulator >= (ticksPerMonth/10)){ monthAccumulator = 0; }
  }

  // Main loop
  let last = performance.now();
  const TICK_HZ = 10;
  const DT = 1.0 / TICK_HZ;

  function frame(now){
    const elapsed = (now - last)/1000;
    last = now;
    // fixed step
    let acc = elapsed;
    while (acc > 0){
      const dt = Math.min(DT, acc);
      step(dt);
      acc -= dt;
      tickCounter++;
      if (tickCounter % 2 === 0) updateUI();
    }
    draw();
    requestAnimationFrame(frame);
  }

  function reset(){
    world.t = 0;
    world.cats = [];
    world.tiles = [];
    world.price = +ui.price.value;
    world.arpu = world.price;
    world.releaseRate = +ui.release.value;
    world.speedMult = +ui.speed.value;
    world.churned = 0;
    world.referrals = 0;
    world.mrr = 0;
    world.cash = 50000;
    placeTile(200, GROUND_Y-32, 'ramp', 1);
    placeTile(360, GROUND_Y-32, 'toy', 1);
    placeTile(520, GROUND_Y-32, 'pond', 1);
    placeTile(680, GROUND_Y-32, 'billboard', 1);
    placeTile(820, GROUND_Y-32, 'pit', 1);
  }

  requestAnimationFrame(frame);
})();