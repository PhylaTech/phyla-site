// Header condense on scroll, shared across every page.
// GSAP ScrollTrigger scrubs the shrink continuously over the first 120px of scroll
// (progress = scrollY / 120), rAF-batched with a little smoothing lag, so the header
// eases down instead of snapping at a threshold. A class toggled at a scroll threshold
// jittered, because shrinking the sticky header shifted layout back across the threshold
// and the toggle flip-flopped; a single monotonic tween has nothing to oscillate on.
(function () {
  if (!window.gsap || !window.ScrollTrigger) return;
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  var logo = document.querySelector('.site-header .wordmark-svg');
  var inner = document.querySelector('.site-header .header-inner');
  if (!logo || !inner) return;
  gsap.registerPlugin(ScrollTrigger);
  gsap.timeline({ scrollTrigger: { start: 0, end: 120, scrub: 0.35 } })
    .to(logo,  { height: 52, ease: 'none' }, 0)
    .to(inner, { paddingTop: 6, paddingBottom: 6, ease: 'none' }, 0);
})();
