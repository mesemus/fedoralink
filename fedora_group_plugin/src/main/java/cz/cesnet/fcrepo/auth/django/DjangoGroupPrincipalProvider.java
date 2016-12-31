/*
 * Licensed to DuraSpace under one or more contributor license agreements.
 * See the NOTICE file distributed with this work for additional information
 * regarding copyright ownership.
 *
 * DuraSpace licenses this file to you under the Apache License,
 * Version 2.0 (the "License"); you may not use this file except in
 * compliance with the License.  You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
package cz.cesnet.fcrepo.auth.django;

import org.fcrepo.auth.common.HttpHeaderPrincipalProvider;
import org.fcrepo.auth.common.ServletContainerAuthenticationProvider;
import org.modeshape.jcr.api.ServletCredentials;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import javax.jcr.Credentials;
import javax.servlet.http.HttpServletRequest;
import java.security.Principal;
import java.util.Set;

import static java.util.Collections.emptySet;

/**
 * A principal provider that adds django groups passed in On-Behalf-Of-Django-Group as principals.
 *
 * @author Mirek Simek
 * @see HttpHeaderPrincipalProvider
 */
@SuppressWarnings("unused")
public class DjangoGroupPrincipalProvider extends HttpHeaderPrincipalProvider {

    private static final Logger LOGGER = LoggerFactory.getLogger(DjangoGroupPrincipalProvider.class);

    /**
     * default constructor for creating an instance of the provider
     */
    public DjangoGroupPrincipalProvider() {
        setHeaderName("On-Behalf-Of-Django-Groups");
        setSeparator(",");
    }

    @Override
    public Set<Principal> getPrincipals(final Credentials credentials) {

        if (!(credentials instanceof ServletCredentials)) {
            LOGGER.debug("Credentials is not an instanceof ServletCredentials");
            return emptySet();
        }

        final ServletCredentials servletCredentials =
                (ServletCredentials) credentials;

        final HttpServletRequest request = servletCredentials.getRequest();

        if (request == null) {
            LOGGER.debug("Servlet request from servletCredentials was null");
            return emptySet();
        }

        if (!request.isUserInRole(ServletContainerAuthenticationProvider.FEDORA_ADMIN_ROLE)) {
            LOGGER.debug("Requesting user is not an admin, returning an empty set of credentials");
            return emptySet();
        }

        return super.getPrincipals(credentials);
    }
}
