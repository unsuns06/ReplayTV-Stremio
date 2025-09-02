<PRD>
  <Title>ReplayTV‑Stremio Proxy‑First Streaming Architecture</Title>
  <Date>2025‑09‑01</Date>
  <Author>YourName</Author>
  <Version>1.0</Version>
  
  <Overview>
    This PRD details the technical specifications for transforming the ReplayTV‑Stremio add-on into a robust, deployment-agnostic streaming solution that utilizes a proxy-first architecture. All stream media URLs, including meta requests such as catalog resolutions and stream resolve tests, must be routed through a media proxy to inject necessary headers, preserve viewer IP for geo/CDN checks, and ensure consistent cross-platform playback.
  </Overview>
  
  <Goals>
    <Goal>Replace direct broadcaster fetches with proxied URLs for all media streams.</Goal>
    <Goal>Implement a proxy infrastructure that injects client-specific headers (Referer, User-Agent, Origin) for all requests, including meta requests.</Goal>
    <Goal>Ensure viewer IP is prioritized and forwarded to upstream servers to satisfy geo-restriction and CDN policies during all interactions.</Goal>
    <Goal>Expose configuration toggles (e.g., Headers ON/OFF) to adapt playback compatibility across different clients.</Goal>
    <Goal>Develop diagnostic and health endpoints for deployment visibility and troubleshooting.</Goal>
  </Goals>
  
  <Features>
    <Feature>
      <Title>Proxied Stream URLs</Title>
      <Description>All media stream links returned to clients (HLS/DASH) must be replaced with URLs pointing to the media proxy service. These URLs should include query parameters that specify the upstream URL and header directives for injection. This includes live streams, replays, and playlist segments.</Description>
    </Feature>
    <Feature>
      <Title>Meta-Requests Proxying</Title>
      <Description>Catalog requests (/catalog/*), stream resolution (/resolve), and diagnostic endpoints (/debug/resolve, /debug/ip) should all route through the same media proxy infrastructure, ensuring viewer IP trustworthiness and consistency in CDN/geo policies.</Description>
    </Feature>
    <Feature>
      <Title>Viewer IP Attestation</Title>
      <Description>The viewer's IP address must be forwarded via headers (X-Forwarded-For, Forwarded) to upstream servers and proxy endpoints, ensuring geo/CDN checks evaluate the user's network location, not the server’s.</Description>
    </Feature>
    <Feature>
      <Title>Configurable Headers Toggle</Title>
      <Description>A UI/config parameter to switch header injection ON/OFF, allowing compatibility with different players (e.g., ExoPlayer/Android TV) by toggling custom headers like Referer, User-Agent, and Origin.</Description>
    </Feature>
    <Feature>
      <Title>Operational Diagnostic Endpoints</Title>
      <Description>Implement health (/health), IP debug (/debug/ip), URL resolve (/debug/resolve), and cache status (/cache/status) endpoints for monitoring, debugging, and troubleshooting.</Description>
    </Feature>
    <Feature>
      <Title>Proxy Setup & Deployment</Title>
      <Description>The proxy component (e.g., MediaFlow Proxy) must be deployed separately or integrated, with environment variables controlling proxy URL, header options, and routing behaviors. It must handle playlist rewriting, segment routing, and header injection seamlessly.</Description>
    </Feature>
  </Features>
  
  <TechnicalDetails>
    <Section>
      <Title>1. Proxy URL Building</Title>
      <Description>
        All stream URLs returned to the client should be constructed via a proxy pattern:
        <ul>
          <li>Base URL: <PROXY_BASE_URL></li>
          <li>Query Params:
            <ul>
              <li>url: upstream media URL (HLS/DASH)</li>
              <li>h_referer (optional): to spoof the Referer header</li>
              <li>h_user-agent (optional): to mimic browser User-Agent</li>
              <li>h_origin (optional): originating domain/URL</li>
              <li>force_playlist_proxy (optional): boolean to route playlist segments via proxy</li>
            </ul>
          </li>
        </ul>
      </Description>
    </Section>
    <Section>
      <Title>2. All Meta Requests Must Be Proxied</Title>
      <Description>
        The following endpoints must route through the proxy system, ensuring they include viewer IP and headers:
        <ul>
          <li>Catalog fetches (/catalog) for channel lists and EPG data</li>
          <li>Resolution tests (/debug/resolve)</li>
          <li>Stream metadata resolution (/resolve, /stream)</li>
        </ul>
        These requests should produce responses with proxied URLs containing header parameters as needed.
      </Description>
    </Section>
    <Section>
      <Title>3. Viewer IP Handling</Title>
      <Description>
        The viewer's IP address is sent via the X-Forwarded-For header or equivalent to the proxy endpoint, which then forwards this IP during upstream requests. The proxy and upstream servers must be configured to prioritize this IP for geo/CDN policies.
      </Description>
    </Section>
    <Section>
      <Title>4. Configuration & Toggle UI</Title>
      <Description>
        The add-on should include a configuration UI or manifest parameter to toggle header injection. When enabled, stream URLs embed headers; when disabled, streams are returned without custom headers for compatibility.
      </Description>
    </Section>
    <Section>
      <Title>5. Diagnostic Endpoints</Title>
      <Description>
        Implement API endpoints for:
        <ul>
          <li>/health: status and version</li>
          <li>/debug/ip: client IP info</li>
          <li>/debug/resolve?url=: upstream URL status</li>
          <li>/cache/status: catalog cache info</li>
        </ul>
        These facilitate deployment troubleshooting and ensure the proxy path functions as intended.
      </Description>
    </Section>
  </TechnicalDetails>
  
  <DeploymentRequirements>
    <Requirement>
      <Title>Proxy deployment</Title>
      <Description>Deploy the media proxy (e.g., MediaFlow Proxy) separately, ensuring it is secure, accessible via HTTPS, and configured with environment variables for proxy URL, header toggles, and routing options similar to existing proven setups.</Description>
    </Requirement>
    <Requirement>
      <Title>Python add-on modification</Title>
      <Description>Amend the stream handler to generate proxied URLs with current request parameters and headers, replacing direct media links; include viewer IP forwarding and toggleability.</Description>
    </Requirement>
    <Requirement>
      <Title>Configurable toggles</Title>
      <Description>Implement a persistent toggle for headers and proxy modes, configurable via UI or manifest params, that influence URL construction.</Description>
    </Requirement>
  </DeploymentRequirements>
  
  <AcceptanceCriteria>
    <Criterion>All video streams, replay, and live channels are playable through Stremio using proxied URLs with header injection enabled.</Criterion>
    <Criterion>Meta requests (catalog, resolve, debug endpoints) route through the same proxy, ensuring viewer IP is used for geo/CDN policies.</Criterion>
    <Criterion>User configuration toggle for headers influences generated stream URLs during runtime.</Criterion>
    <Criterion>Diagnostic endpoints provide accurate viewer IP, resolution, and cache status info.</Criterion>
    <Criterion>Deployment with proxy setup results in reliable playback across all supported platforms, passing CORS, Referer, User-Agent, and geo restrictions.</Criterion>
  </AcceptanceCriteria>
  
  <Notes>
    - All requests to upstream media sources must be through the proxy, never direct fetches.
    - Viewer IP is critical for geo/CDN checks and must be passed on all meta and media requests.
    - Proxy must support playlist manifest rewriting and segment proxying with minimal latency.
    - Maintain the current curated French source catalog with local caching; do not hard-code upstream URLs.
    - The solution should be modular to allow switching between direct and proxied modes via configuration.
  </Notes>
</PRD>
