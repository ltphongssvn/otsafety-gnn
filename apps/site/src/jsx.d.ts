// apps/site/src/jsx.d.ts
// The site's own JSX element type, so no framework has to supply one.
//
// Astro declares astroHTML.JSX.Element as `HTMLElement | any`, and resolves that
// `any` through whichever UI framework provides JSX types. React was the only one
// this site declared, and nothing rendered with it -- so removing it left every
// .astro template returning a type typescript-eslint could not resolve, and the
// type-aware rules reported fourteen no-unsafe-return errors.
//
// eslint-plugin-astro documents this exact case and this exact remedy: a project
// with no framework present overrides JSX.Element itself. The site renders HTML,
// so HTMLElement is what its templates return.
//
// IT PASSED LOCALLY AND FAILED IN CI because bun install left React in
// node_modules after it was removed from package.json; a clean install, which is
// what CI performs, reproduced all fourteen.
import "astro/astro-jsx";

declare global {
  namespace JSX {
    type Element = HTMLElement;
  }
}
